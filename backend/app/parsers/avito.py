"""Avito — парсер вакансий через Playwright (headless Chromium).

У Avito анти-бот DataDome: JS-проверка, которую не пройти простым HTTP.
Открываем страницы настоящим headless-браузером в отдельном контейнере
(Dockerfile.avito + app/avito_worker.py).

ВАЖНО: для браузера нужен СТАТИЧНЫЙ (sticky) прокси — ротационный рвёт
навигацию посреди загрузки. Поэтому отдельная переменная AVITO_PROXY.

При срабатывании анти-бота парсер возвращает [] и пишет warning.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import Any
from urllib.parse import unquote, urlencode, urlparse

from ..config import settings
from ..schemas import VacancyDTO
from .base import BaseParser

logger = logging.getLogger(__name__)


AVITO_QUERIES = [
    "подработка школьник",
    "курьер",
    "промоутер",
    "официант",
    "бариста",
    "помощник",
    "расклейщик",
    "грузчик подработка",
]

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = {runtime: {}};
"""


def _parse_proxy_url(url: str) -> dict | None:
    """Превращает 'http://user:pass@host:port' в формат proxy для Playwright.

    username/password в URL обычно URL-кодированы (';' → '%3B') — Playwright
    принимает их отдельными полями, поэтому возвращаем через unquote.
    """
    url = (url or "").strip()
    if not url:
        return None
    try:
        p = urlparse(url)
    except ValueError:
        return None
    if not p.hostname:
        return None
    scheme = p.scheme or "http"
    server = f"{scheme}://{p.hostname}"
    if p.port:
        server += f":{p.port}"
    out: dict[str, str] = {"server": server}
    if p.username:
        out["username"] = unquote(p.username)
    if p.password:
        out["password"] = unquote(p.password)
    return out


class AvitoParser(BaseParser):
    source = "avito"
    BASE = "https://www.avito.ru"
    SEARCH_PATH = "/all/vakansii"

    def __init__(self, client: Any = None, **opts):
        # httpx-клиент Avito не нужен — ходим через Playwright.
        super().__init__(client=client, **opts)

    async def fetch(self, *, limit: int = 50) -> list[VacancyDTO]:
        if not settings.avito_enabled:
            logger.info("Avito disabled (AVITO_ENABLED=false)")
            return []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright не установлен — AvitoParser пропущен")
            return []

        out: list[VacancyDTO] = []
        seen: set[str] = set()
        per_query = max(5, limit // len(AVITO_QUERIES))
        # Для браузера нужен СТАТИЧНЫЙ IP — ротационный рвёт навигацию.
        proxy = _parse_proxy_url(settings.avito_effective_proxy)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                proxy=proxy,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu",
                ],
            )
            try:
                context = await browser.new_context(
                    user_agent=BROWSER_UA,
                    viewport={"width": 1366, "height": 768},
                    locale="ru-RU",
                    timezone_id="Europe/Moscow",
                )
                await context.add_init_script(_STEALTH_JS)

                # «Прогрев»: заходим на главную, получаем DataDome-куки,
                # имитируем что пришёл живой пользователь — потом поиск
                # проходит мягче.
                warm = await context.new_page()
                try:
                    await warm.goto(
                        "https://www.avito.ru/", wait_until="domcontentloaded",
                        timeout=35000,
                    )
                    await warm.wait_for_timeout(3000)
                    await warm.mouse.wheel(0, 1200)
                    await warm.wait_for_timeout(1500)
                except Exception as e:  # noqa: BLE001
                    logger.debug("avito warmup failed: %s", e)
                finally:
                    await warm.close()

                for q in AVITO_QUERIES:
                    if len(out) >= limit:
                        break
                    # Свежая страница на каждый запрос: упавшая навигация
                    # не отравляет последующие.
                    page = await context.new_page()
                    try:
                        cards = await self._search(page, q, per_query)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("avito search %r failed: %s", q, e)
                        cards = []
                    finally:
                        await page.close()

                    for c in cards:
                        ext_id = c.get("external_id")
                        if not ext_id or ext_id in seen:
                            continue
                        seen.add(ext_id)
                        out.append(self._map(c))
                        if len(out) >= limit:
                            break
                    # Длинная случайная пауза — DataDome триггерится на
                    # быструю серию запросов. 8-16 сек между поисками.
                    await asyncio.sleep(random.uniform(8.0, 16.0))
            finally:
                await browser.close()

        if not out:
            logger.info(
                "AvitoParser: ничего не получено — вероятно anti-bot DataDome."
            )
        return out

    async def _search(self, page: Any, query: str, limit: int) -> list[dict[str, Any]]:
        params = urlencode({"q": query, "s": "104"})  # s=104 — сортировка по дате
        url = f"{self.BASE}{self.SEARCH_PATH}?{params}"

        # Навигация с ретраями: одна неудачная попытка не должна ронять запрос.
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=35000)
                last_err = None
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.debug("avito goto attempt %d failed: %s", attempt + 1, e)
                await asyncio.sleep(2.0 * (attempt + 1))
        if last_err is not None:
            raise last_err

        # Имитируем живого пользователя: лёгкий скролл, человекоподобные
        # паузы. DataDome-challenge часто JS-based и решается сам, если
        # дать странице «пожить» и проскроллить.
        async def _looks_loaded() -> bool:
            try:
                await page.wait_for_selector(
                    '[data-marker="item"]', timeout=12000
                )
                return True
            except Exception:  # noqa: BLE001
                return False

        if not await _looks_loaded():
            # Возможно DataDome-challenge — даём ему время, скроллим, ждём.
            for _ in range(3):
                await page.mouse.wheel(0, random.randint(600, 1400))
                await page.wait_for_timeout(random.randint(2500, 4500))
                if await _looks_loaded():
                    break
            else:
                logger.warning(
                    "avito: no item cards for %r (anti-bot challenge?)", query
                )
                return []

        await page.wait_for_timeout(random.randint(1000, 2200))
        html = await page.content()
        return self._extract_from_html(html, limit)

    # ── Парсинг HTML (bs4 / JSON-LD) ──────────────────────────────────

    @classmethod
    def _extract_from_html(cls, html: str, limit: int) -> list[dict[str, Any]]:
        from bs4 import BeautifulSoup

        out: list[dict[str, Any]] = []
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

        cards = soup.select('div[data-marker="item"]')
        for c in cards:
            parsed = cls._parse_card(c)
            if parsed:
                if any(p.get("external_id") == parsed["external_id"] for p in out):
                    continue
                out.append(parsed)
                if len(out) >= limit:
                    break
        return out

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
        ext_id = re.sub(r"^i", "", str(ext_id))

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

    @staticmethod
    def _parse_salary_struct(obj: dict[str, Any]):
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
            "HOUR": "/час", "DAY": "/день", "WEEK": "/неделя",
            "MONTH": "/мес", "YEAR": "/год",
        }
        return sf, st, unit_map.get(str(unit_text).upper(), "/мес")

    @staticmethod
    def _parse_salary_text(raw: str):
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
    if "<" not in html:
        return re.sub(r"\s+", " ", html).strip()
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
