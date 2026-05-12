"""SuperJob — парсер через https://api.superjob.ru/2.0/vacancies/."""
from __future__ import annotations

import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..schemas import VacancyDTO
from .base import BaseParser

logger = logging.getLogger(__name__)


SJ_QUERIES = [
    "подработка",
    "курьер",
    "промоутер",
    "репетитор",
    "официант",
    "бариста",
]


class SuperJobParser(BaseParser):
    source = "superjob"
    BASE_URL = "https://api.superjob.ru/2.0/vacancies/"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _search(self, keyword: str, page: int = 0, count: int = 30) -> dict:
        if not settings.superjob_api_key:
            raise RuntimeError("SUPERJOB_API_KEY не задан")
        params = {
            "keyword": keyword,
            "page": page,
            "count": count,
            "order_field": "date",
            "order_direction": "desc",
            # 6 — частичная занятость; работодатель доплат не любит, но MVP-ок.
            "type_of_work": 6,
        }
        headers = {"X-Api-App-Id": settings.superjob_api_key}
        r = await self.client.get(self.BASE_URL, params=params, headers=headers)
        r.raise_for_status()
        return r.json()

    async def fetch(self, *, limit: int = 50) -> list[VacancyDTO]:
        if not settings.superjob_api_key:
            logger.info("SuperJob skipped — нет API ключа")
            return []

        out: list[VacancyDTO] = []
        seen: set[str] = set()
        per_query = max(5, limit // len(SJ_QUERIES))

        for q in SJ_QUERIES:
            if len(out) >= limit:
                break
            try:
                data = await self._search(q, page=0, count=per_query)
            except Exception as e:  # noqa: BLE001
                logger.warning("SuperJob fetch failed for %r: %s", q, e)
                continue

            for item in data.get("objects", []):
                ext_id = str(item.get("id"))
                if not ext_id or ext_id in seen:
                    continue
                seen.add(ext_id)
                out.append(self._map(item))
                if len(out) >= limit:
                    break
        return out

    def _map(self, item: dict) -> VacancyDTO:
        item.get("address") or item.get("town", {}).get("title")
        text_for_age = (item.get("profession") or "") + " " + (item.get("candidat") or "")
        # SuperJob возвращает зарплату в рублях.
        salary_from: int | None = item.get("payment_from") or None
        salary_to: int | None = item.get("payment_to") or None

        return VacancyDTO(
            source="superjob",
            external_id=str(item.get("id")),
            title=item.get("profession", "") or "Без названия",
            company=(item.get("client") or {}).get("title") or item.get("firm_name"),
            description=item.get("candidat") or item.get("work"),
            salary_from=salary_from,
            salary_to=salary_to,
            salary_unit="/мес",
            city=(item.get("town") or {}).get("title"),
            format="online" if item.get("place_of_work", {}).get("id") == 2 else "offline",
            category=(item.get("catalogues") or [{}])[0].get("title") if item.get("catalogues") else None,
            min_age=self.detect_min_age(text_for_age),
            url=item.get("link", ""),
            posted_at=str(item.get("date_published")) if item.get("date_published") else None,
        )
