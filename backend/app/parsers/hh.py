"""hh.ru - парсер через публичный API https://api.hh.ru.

HH блокирует статичный User-Agent с 403. Решение:
- Пул реалистичных UA, рандомный выбор на каждый запрос.
- Заголовок HH-User-Agent с email (как требует hh API).
- Retry с экспоненциальной задержкой.
"""
from __future__ import annotations

import logging
import random

from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..schemas import VacancyDTO
from .base import BaseParser

logger = logging.getLogger(__name__)


HH_QUERIES = [
    "подработка школьник",
    "подработка студент",
    "курьер",
    "промоутер",
    "официант",
    "бариста",
    "репетитор",
    "оператор колл-центр",
]


# Пул User-Agent'ов для ротации - hh.ru блокирует статичные.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def _build_headers() -> dict[str, str]:
    """Случайный UA + HH-User-Agent (hh API требует контактный email)."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "HH-User-Agent": settings.hh_user_agent,
        "Accept": "application/json",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
    }


class HhParser(BaseParser):
    source = "hh"
    BASE_URL = "https://api.hh.ru/vacancies"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def _search(self, text: str, page: int = 0, per_page: int = 30) -> dict:
        # label=accept_kids — официальный фильтр HH «работодатель принимает
        # соискателей от 14 лет». Это **самый точный** источник вакансий
        # для подростков; если у HH-IP жив прокси — даёт золото.
        # Дополнительный label=accept_temporary — временная/разовая занятость.
        params: list[tuple[str, str]] = [
            ("text", text),
            ("page", str(page)),
            ("per_page", str(per_page)),
            ("order_by", "publication_time"),
            ("employment", "part"),
            ("label", "accept_kids"),
            ("label", "accept_temporary"),
        ]
        r = await self.client.get(self.BASE_URL, params=params, headers=_build_headers())
        r.raise_for_status()
        return r.json()

    async def fetch(self, *, limit: int = 50) -> list[VacancyDTO]:
        out: list[VacancyDTO] = []
        seen: set[str] = set()
        per_query = max(5, limit // len(HH_QUERIES))

        for q in HH_QUERIES:
            if len(out) >= limit:
                break
            try:
                data = await self._search(q, page=0, per_page=per_query)
            except Exception as e:  # noqa: BLE001
                logger.warning("hh.ru fetch failed for %r: %s", q, e)
                continue

            for item in data.get("items", []):
                ext_id = str(item.get("id"))
                if not ext_id or ext_id in seen:
                    continue
                seen.add(ext_id)
                out.append(self._map(item))
                if len(out) >= limit:
                    break

        return out

    def _map(self, item: dict) -> VacancyDTO:
        salary = item.get("salary") or {}
        snippet = item.get("snippet") or {}
        text_for_age = " ".join(
            filter(
                None,
                [
                    item.get("name") or "",
                    snippet.get("requirement") or "",
                    snippet.get("responsibility") or "",
                ],
            )
        )

        schedule = (item.get("schedule") or {}).get("name")
        remote = schedule and "удал" in schedule.lower()

        area_name = (item.get("area") or {}).get("name")

        return VacancyDTO(
            source="hh",
            external_id=str(item.get("id")),
            title=item.get("name", ""),
            company=(item.get("employer") or {}).get("name"),
            description=(snippet.get("requirement") or "")
            + ("\n\n" + snippet.get("responsibility") if snippet.get("responsibility") else ""),
            salary_from=salary.get("from"),
            salary_to=salary.get("to"),
            salary_unit="/мес",
            city=area_name,
            format="online" if remote else "offline",
            category=None,
            min_age=self.detect_min_age(text_for_age),
            url=item.get("alternate_url", ""),
            posted_at=item.get("published_at"),
        )
