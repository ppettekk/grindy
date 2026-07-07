"""Rabota.ru - двухступенчатый парсер.

1. Search-страница → ID/title/url + baseSalary (если JSON-LD есть).
2. Для каждой вакансии без city → дёргаем detail-страницу: оттуда вытаскиваем
   addressLocality из JSON-LD. Это даёт нам город, которого нет в search.

Detail-страницы доступны только с «чистого» РФ-IP (через PARSER_PROXY).
Если detail вернул 403/timeout — продолжаем работу без обогащения.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ..schemas import VacancyDTO
from .base import BaseParser, make_async_client

logger = logging.getLogger(__name__)


# Сколько detail-страниц тянем параллельно. Слишком много → анти-бот.
DETAIL_CONCURRENCY = 3
DETAIL_TIMEOUT_SEC = 8.0


# Широкие запросы для максимального покрытия. Релевантность подростковости
# обеспечивает фильтр experience_id=1 (без опыта) и постфильтр is_suitable_for_teen.
RABOTA_QUERIES = [
    "подработка",
    "без опыта",
    "школьник",
    "студент",
    "стажёр",
    "помощник",
    "доставка",
]


# Параметры URL Rabota.ru, которые сужают выдачу под подростков:
# experience_id=1 — «нет опыта»;
# employment_type=part — частичная занятость / подработка.
# Поведение сайта: пустой query всё равно требует параметра, поэтому добавляем
# непустой term, но «широкий» (см. RABOTA_QUERIES).
RABOTA_FILTER_PARAMS = {
    "experience_id": "1",
    "employment_type": "part",
}


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
    "Upgrade-Insecure-Requests": "1",
}


class RabotaParser(BaseParser):
    source = "rabota"
    BASE = "https://www.rabota.ru"
    SEARCH_PATH = "/vacancy"

    def __init__(self, client: httpx.AsyncClient | None = None, **opts):
        client = client or make_async_client(
            headers=BROWSER_HEADERS,
            timeout=httpx.Timeout(25.0, connect=10.0),
            follow_redirects=True,
        )
        super().__init__(client=client, **opts)

    async def fetch(self, *, limit: int = 50) -> list[VacancyDTO]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        per_query = max(5, limit // len(RABOTA_QUERIES))

        # 1) Собираем список из search-страниц.
        for q in RABOTA_QUERIES:
            if len(out) >= limit:
                break
            try:
                items = await self._search(q, per_query)
            except Exception as e:  # noqa: BLE001
                logger.warning("rabota.ru search %r failed: %s", q, e)
                continue
            for it in items:
                ext_id = it.get("external_id")
                if not ext_id or ext_id in seen:
                    continue
                seen.add(ext_id)
                out.append(it)
                if len(out) >= limit:
                    break

        # 2) Обогащаем detail-страницами те, у которых нет city/зарплаты.
        #    Поскольку search Rabota не отдаёт addressLocality, без этого шага
        #    у нас не будет городов и фильтр «Москва» ничего не выдаст.
        missing = [
            it for it in out
            if not it.get("city")
            or (not it.get("salary_from") and not it.get("salary_to"))
        ]
        if missing:
            logger.info(
                "rabota.ru: enriching %d items via detail pages", len(missing)
            )
            await self._enrich_with_details(missing)

        if not out:
            logger.info("RabotaParser: ничего не получено.")
        return [self._map(it) for it in out]

    async def _enrich_with_details(self, items: list[dict[str, Any]]) -> None:
        """Параллельно тянет detail-страницы и пишет city/salary в items in-place.

        Любая ошибка (403/timeout/parsing) тихо игнорируется — мы не валим
        ingest из-за одной вакансии. Если detail-страницы вообще закрыты —
        исходные данные из search остаются без изменений.
        """
        sem = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async def one(it: dict[str, Any]) -> None:
            async with sem:
                url = it.get("url")
                if not url:
                    return
                try:
                    r = await asyncio.wait_for(
                        self.client.get(url), timeout=DETAIL_TIMEOUT_SEC
                    )
                except (TimeoutError, asyncio.TimeoutError):
                    return
                except Exception as e:  # noqa: BLE001
                    logger.debug("rabota detail %s error: %s", url, e)
                    return
                if r.status_code != 200:
                    return
                enriched = self._parse_detail(r.text)
                if enriched:
                    for k, v in enriched.items():
                        if v is not None and not it.get(k):
                            it[k] = v

        await asyncio.gather(*(one(i) for i in items))

    @classmethod
    def _parse_detail(cls, html: str) -> dict[str, Any] | None:
        """Парсит JSON-LD JobPosting со страницы конкретной вакансии."""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            for item in cls._iter_jobpostings(data):
                parsed = cls._from_jobposting(item)
                if parsed:
                    return parsed
        return None

    async def _search(self, query: str, limit: int) -> list[dict[str, Any]]:
        params = {"query": query, **RABOTA_FILTER_PARAMS}
        r = await self.client.get(self.BASE + self.SEARCH_PATH, params=params)
        if r.status_code in (403, 429):
            logger.warning("rabota.ru anti-bot %s for %r", r.status_code, query)
            return []
        if r.status_code != 200:
            logger.warning("rabota.ru unexpected %s for %r", r.status_code, query)
            return []
        return self._extract_from_html(r.text, limit)

    # ── Парсинг search-страницы ────────────────────────────────────────

    @classmethod
    def _extract_from_html(cls, html: str, limit: int) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        out: list[dict[str, Any]] = []

        # JSON-LD JobPosting (если есть)
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

        # DOM-fallback: ссылки на /vacancy/<id>
        seen_urls: set[str] = {p["url"] for p in out if p.get("url")}
        for a in soup.select("a[href*='/vacancy/']"):
            href = a.get("href", "")
            if not re.search(r"/vacancy/\d+/?$", href):
                continue
            url = href if href.startswith("http") else f"https://www.rabota.ru{href}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            ext_id = cls._ext_id_from_url(url)
            if not ext_id:
                continue
            title = a.get_text(strip=True) or "Вакансия"
            out.append(
                {
                    "external_id": ext_id,
                    "title": title,
                    "url": url,
                    "company": None,
                    "city": None,
                    "description": None,
                    "salary_from": None,
                    "salary_to": None,
                    "salary_unit": "/мес",
                    "remote": False,
                    "posted_at": None,
                }
            )
            if len(out) >= limit:
                break
        return out

    # ── Хелперы ────────────────────────────────────────────────────────

    @staticmethod
    def _iter_jobpostings(node: Any):
        if isinstance(node, dict):
            t = node.get("@type")
            if t == "JobPosting":
                yield node
            elif t == "ItemList":
                for el in node.get("itemListElement", []) or []:
                    if isinstance(el, dict):
                        item = el.get("item") or el
                        yield from RabotaParser._iter_jobpostings(item)
            elif "@graph" in node:
                yield from RabotaParser._iter_jobpostings(node["@graph"])
        elif isinstance(node, list):
            for el in node:
                yield from RabotaParser._iter_jobpostings(el)

    @classmethod
    def _from_jobposting(cls, item: dict[str, Any]) -> dict[str, Any] | None:
        url = item.get("url") or ""
        if not url:
            return None
        ext_id = cls._ext_id_from_url(url)
        if not ext_id:
            return None

        salary_from, salary_to, salary_unit = cls._parse_salary_struct(
            item.get("baseSalary") or {}
        )

        loc = item.get("jobLocation") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        addr = loc.get("address") if isinstance(loc, dict) else {}
        city = addr.get("addressLocality") if isinstance(addr, dict) else None

        org = item.get("hiringOrganization") or {}
        company = org.get("name") if isinstance(org, dict) else None

        remote = (item.get("jobLocationType") or "").upper() == "TELECOMMUTE"

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
            "remote": remote,
            "posted_at": item.get("datePosted"),
        }

    @staticmethod
    def _ext_id_from_url(url: str) -> str | None:
        m = re.search(r"/vacancy/(\d{4,})", url)
        return m.group(1) if m else None

    @staticmethod
    def _parse_salary_struct(obj: dict[str, Any]) -> tuple[int | None, int | None, str | None]:
        """Парсит baseSalary в любой из форм JSON-LD MonetaryAmount.

        Видимые в природе варианты:
        A. obj = {minValue, maxValue, unitText, ...}                — плоский
        B. obj = {value: {minValue, maxValue, unitText}}            — всё в value
        C. obj = {value: число, unitText: ...}                     — одно число
        D. obj = {minValue, maxValue, value: {unitText, ...}}      — Rabota.ru search:
           min/max на верху, в value только unit.
        E. value = QuantitativeValue с value=число                  — fallback
        """
        if not obj or not isinstance(obj, dict):
            return None, None, None

        value = obj.get("value")

        # Берём min/max сначала с верхнего уровня (форма A, D).
        min_v = obj.get("minValue")
        max_v = obj.get("maxValue")
        unit_text = obj.get("unitText")

        if isinstance(value, dict):
            # Формы B/D: значения в value приоритетнее, если они есть.
            if value.get("minValue") is not None:
                min_v = value.get("minValue")
            if value.get("maxValue") is not None:
                max_v = value.get("maxValue")
            # Форма E: внутренний QuantitativeValue.value
            inner = value.get("value")
            if inner is not None and min_v is None and max_v is None:
                min_v = max_v = inner
            if value.get("unitText"):
                unit_text = value.get("unitText")
        elif value is not None:
            # Форма C: value = число.
            if min_v is None and max_v is None:
                min_v = max_v = value

        if unit_text is None:
            unit_text = "MONTH"

        def _to_int(x: Any) -> int | None:
            # Отбрасываем None/""/0, чтобы "от 0" не превращалось в "от 0₽".
            if x in (None, "", 0, "0"):
                return None
            try:
                return int(float(x))
            except (TypeError, ValueError):
                return None

        sf = _to_int(min_v)
        st = _to_int(max_v)

        unit_map = {
            "HOUR": "/час",
            "DAY": "/день",
            "WEEK": "/неделя",
            "MONTH": "/мес",
            "YEAR": "/год",
        }
        return sf, st, unit_map.get(str(unit_text).upper(), "/мес")

    def _map(self, it: dict[str, Any]) -> VacancyDTO:
        text_for_age = (it.get("title") or "") + " " + (it.get("description") or "")
        fmt = "online" if it.get("remote") else "offline"
        return VacancyDTO(
            source="rabota",
            external_id=it["external_id"],
            title=it["title"] or "Без названия",
            company=it.get("company"),
            description=it.get("description"),
            salary_from=it.get("salary_from"),
            salary_to=it.get("salary_to"),
            salary_unit=it.get("salary_unit") or "/мес",
            city=it.get("city"),
            format=fmt,
            category=None,
            min_age=self.detect_min_age(text_for_age),
            url=it["url"],
            posted_at=it.get("posted_at"),
        )


def _clean_text(html: str) -> str:
    if not html:
        return ""
    if "<" not in html:
        return re.sub(r"\s+", " ", html).strip()
    soup = BeautifulSoup(html, "lxml")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
