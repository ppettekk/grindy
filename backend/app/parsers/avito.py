"""Avito — парсер поисковой страницы вакансий.

У Avito нет публичного API. Идём через HTML страницы /all/vakansii с
браузероподобными заголовками и парсим карточки через bs4.
При срабатывании anti-bot (403/429) парсер возвращает пустой список и
пишет warning — ingest продолжит работу с другими источниками.

Если на проде anti-bot будет резать постоянно, можно поднять флаг
``AVITO_ENABLED=false`` или подменить fetch на headless-вариант через
Playwright (см. README.md).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ..schemas import VacancyDTO
from .base import BaseParser, make_async_client

logger = logging.getLogger(__name__)


AVITO_QUERIES = [
    "подработка школьник",
    "курьер",
    "промоутер",
    "официант",
    "бариста",
    "репетитор",
]

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class AvitoParser(BaseParser):
    source = "avito"
    BASE = "https://www.avito.ru"
    SEARCH_PATH = "/all/vakansii"

    def __init__(self, client: httpx.AsyncClient | None = None, **opts):
        client = client or make_async_client(
            headers=BROWSER_HEADERS,
            timeout=httpx.Timeout(25.0, connect=10.0),
            follow_redirects=True,
        )
        super().__init__(client=client, **opts)

    async def fetch(self, *, limit: int = 50) -> list[VacancyDTO]:
        out: list[VacancyDTO] = []
        seen: set[str] = set()
        per_query = max(5, limit // len(AVITO_QUERIES))

        for q in AVITO_QUERIES:
            if len(out) >= limit:
                break
            try:
                cards = await self._search(q, per_query)
            except Exception as e:  # noqa: BLE001
                logger.warning("avito search %r failed: %s", q, e)
                continue
            for c in cards:
                ext_id = c.get("external_id")
                if not ext_id or ext_id in seen:
                    continue
                seen.add(ext_id)
                out.append(self._map(c))
                if len(out) >= limit:
                    break

        if not out:
            logger.info(
                "AvitoParser: ничего не получено — вероятно, anti-bot. "
                "Парсер вернул пустой список."
            )
        return out

    async def _search(self, query: str, limit: int) -> list[dict[str, Any]]:
        params = {"q": query, "s": "104"}  # s=104 — сортировка по дате
        r = await self.client.get(self.BASE + self.SEARCH_PATH, params=params)
        if r.status_code in (403, 429):
            logger.warning("avito anti-bot %s for %r", r.status_code, query)
            return []
        if r.status_code != 200:
            logger.warning("avito unexpected %s for %r", r.status_code, query)
            return []
        return self._extract_from_html(r.text, limit)

    # Парсинг HTML

    @classmethod
    def _extract_from_html(cls, html: str, limit: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        # 1) JSON-LD — самый стабильный путь, если он есть
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            for item in cls._iter_jobpostings(data):
                parsed = cls._from_jobposting(item)
                if parsed:
                    out.append(parsed)
                    if len(out) >= limit:
                        return out

        # 2) DOM-fallback: карточки с data-marker="item"
        cards = soup.select('div[data-marker="item"]')
        for c in cards:
            parsed = cls._parse_card(c)
            if parsed:
                # avoid duplicates already added через JSON-LD
                if any(p.get("external_id") == parsed["external_id"] for p in out):
                    continue
                out.append(parsed)
                if len(out) >= limit:
                    break
        return out

    @staticmethod
    def _iter_jobpostings(node: Any):
        """Рекурсивно достаёт JobPosting-ноды из JSON-LD."""
        if isinstance(node, dict):
            t = node.get("@type")
            if t == "JobPosting":
                yield node
            elif t == "ItemList":
                for el in node.get("itemListElement", []) or []:
                    if isinstance(el, dict):
                        item = el.get("item") or el
                        yield from AvitoParser._iter_jobpostings(item)
            elif "@graph" in node:
                yield from AvitoParser._iter_jobpostings(node["@graph"])
        elif isinstance(node, list):
            for el in node:
                yield from AvitoParser._iter_jobpostings(el)

    @classmethod
    def _from_jobposting(cls, item: dict[str, Any]) -> dict[str, Any] | None:
        url = item.get("url") or ""
        if not url:
            return None
        # external_id из URL: https://www.avito.ru/.../vakansiya_..._1234567890
        m = re.search(r"_(\d{6,})(?:[/?#]|$)", url)
        if not m:
            return None
        ext_id = m.group(1)

        salary_obj = item.get("baseSalary") or {}
        salary_from, salary_to, salary_unit = cls._parse_salary_struct(salary_obj)

        loc = item.get("jobLocation") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        addr = (loc.get("address") if isinstance(loc, dict) else {}) or {}
        city = addr.get("addressLocality") if isinstance(addr, dict) else None

        org = item.get("hiringOrganization") or {}
        company = org.get("name") if isinstance(org, dict) else None

        return {
            "external_id": ext_id,
            "title": (item.get("title") or "").strip(),
            "url": url,
            "company": company,
            "city": city,
            "description": _clean_text(item.get("description") or ""),
            "salary_from": salary_from,
            "salary_to": salary_to,
            "salary_unit": salary_unit,
            "remote": (item.get("jobLocationType") or "").upper() == "TELECOMMUTE",
            "posted_at": item.get("datePosted"),
        }

    @classmethod
    def _parse_card(cls, card) -> dict[str, Any] | None:
        ext_id = card.get("data-item-id") or card.get("id")
        if not ext_id:
            return None
        ext_id = re.sub(r"^i", "", str(ext_id))  # иногда "i123456"

        a = card.select_one('a[data-marker="item-title"]')
        if not a:
            return None
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not href:
            return None
        url = href if href.startswith("http") else f"https://www.avito.ru{href}"

        price_el = card.select_one('[data-marker="item-price"]')
        salary_from, salary_to, salary_unit = cls._parse_salary_text(
            price_el.get_text(" ", strip=True) if price_el else ""
        )

        company_el = card.select_one('[data-marker="item-company-name"]')
        company = company_el.get_text(strip=True) if company_el else None

        location_el = card.select_one('[data-marker="item-address"]')
        city = None
        if location_el:
            city_text = location_el.get_text(" ", strip=True)
            city = city_text.split(",")[0].strip() or None

        descr_el = card.select_one('[data-marker="item-specific-params"]')
        description = descr_el.get_text(" ", strip=True) if descr_el else None

        return {
            "external_id": str(ext_id),
            "title": title,
            "url": url,
            "company": company,
            "city": city,
            "description": description,
            "salary_from": salary_from,
            "salary_to": salary_to,
            "salary_unit": salary_unit,
            "remote": False,
            "posted_at": None,
        }

    # Зарплата

    @staticmethod
    def _parse_salary_struct(obj: dict[str, Any]) -> tuple[int | None, int | None, str | None]:
        """Парсинг baseSalary из JSON-LD."""
        if not obj or not isinstance(obj, dict):
            return None, None, None
        value = obj.get("value")
        if isinstance(value, dict):
            min_v = value.get("minValue") or value.get("value")
            max_v = value.get("maxValue") or value.get("value")
            unit_text = value.get("unitText") or "MONTH"
        else:
            min_v = max_v = value
            unit_text = "MONTH"
        try:
            sf = int(min_v) if min_v not in (None, "") else None
            st = int(max_v) if max_v not in (None, "") else None
        except (TypeError, ValueError):
            sf, st = None, None
        unit_map = {
            "HOUR": "/час",
            "DAY": "/день",
            "WEEK": "/неделя",
            "MONTH": "/мес",
            "YEAR": "/год",
        }
        return sf, st, unit_map.get(str(unit_text).upper(), "/мес")

    @staticmethod
    def _parse_salary_text(raw: str) -> tuple[int | None, int | None, str | None]:
        if not raw:
            return None, None, None
        text = raw.replace("\xa0", " ").lower()
        nums = [int(s.replace(" ", "")) for s in re.findall(r"\d[\d ]+", text)]
        if not nums:
            single = re.findall(r"\d+", text)
            nums = [int(x) for x in single] if single else []
        if not nums:
            return None, None, None

        unit = "/мес"
        if "смен" in text:
            unit = "/смену"
        elif "час" in text:
            unit = "/час"
        elif "день" in text or "за день" in text:
            unit = "/день"

        if "от" in text and "до" in text and len(nums) >= 2:
            return nums[0], nums[1], unit
        if "от" in text:
            return nums[0], None, unit
        if "до" in text:
            return None, nums[0], unit
        if len(nums) >= 2:
            return nums[0], nums[1], unit
        return nums[0], None, unit

    # DTO mapping

    def _map(self, c: dict[str, Any]) -> VacancyDTO:
        text_for_age = (c.get("title") or "") + " " + (c.get("description") or "")
        fmt = "online" if c.get("remote") else "offline"
        return VacancyDTO(
            source="avito",
            external_id=c["external_id"],
            title=c["title"] or "Без названия",
            company=c.get("company"),
            description=c.get("description"),
            salary_from=c.get("salary_from"),
            salary_to=c.get("salary_to"),
            salary_unit=c.get("salary_unit") or "/мес",
            city=c.get("city"),
            format=fmt,
            category=None,
            min_age=self.detect_min_age(text_for_age),
            url=c["url"],
            posted_at=c.get("posted_at"),
        )


def _clean_text(html: str) -> str:
    if not html:
        return ""
    # Если разметки нет — bs4 не нужен (и сам бы предупреждал, что строка похожа на URL/файл).
    if "<" not in html:
        return re.sub(r"\s+", " ", html).strip()
    soup = BeautifulSoup(html, "lxml")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
