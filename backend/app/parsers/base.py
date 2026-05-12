from __future__ import annotations

import abc
import logging
import re
from typing import Any

import httpx

from ..config import settings
from ..schemas import VacancyDTO

logger = logging.getLogger(__name__)


# ─── Регулярки для detect_min_age ─────────────────────────────────────────
# Все требуют контекста («лет», «года», «+», «с N лет» и т.п.), чтобы не
# путать с числами в зарплате или часах.
_AGE_NUMBER_PATTERNS: tuple[re.Pattern[str], ...] = (
    # «от 14 лет», «от 18 года»
    re.compile(r"\bот\s+(\d{1,2})\s*(?:лет|года?)\b", re.IGNORECASE),
    # «14+», «18+» — должен идти после слова или начала строки
    re.compile(r"(?<![\d.])\b(\d{1,2})\s*\+(?!\d)"),
    # «минимум 16 лет»
    re.compile(r"\bминимум\s+(\d{1,2})\s*(?:лет|года?)\b", re.IGNORECASE),
    # «с 16 лет», «трудоустройство с 14», «принимаем с 18»
    re.compile(r"\bс\s+(\d{1,2})\s+(?:лет|года?)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:трудоустройство|принимаем|оформление)\s+с\s+(\d{1,2})\b",
        re.IGNORECASE,
    ),
    # «от 18 до 25 лет» — берём нижнюю границу
    re.compile(r"\bот\s+(\d{1,2})\s+до\s+\d{1,2}\s*(?:лет|года?)\b", re.IGNORECASE),
    # «возраст: 16-18 лет», «16-25 лет», «16 - 25 лет»
    re.compile(r"\b(\d{1,2})\s*[–—-]\s*\d{1,2}\s*(?:лет|года?)\b", re.IGNORECASE),
)

# Подростковые сигналы → подмешиваем age=14 в кандидаты.
# NB: «подросток» в склонении превращается в «подростк-», поэтому корень
# без -ок (русское чередование о/ноль). Иначе «подросткам» не сматчится.
_RE_TEEN_TEXT_HINTS = re.compile(
    r"(?:"
    r"\bшкольник"
    r"|\bподростк"
    r"|\bдля\s+школьник"
    r"|\bнесовершеннолетним\s+(?:можно|разрешено|подходит)"
    r"|accept[\s_-]?kids"
    r")",
    re.IGNORECASE,
)

# Взрослые сигналы → подмешиваем age=18.
_RE_ADULT_TEXT_HINTS = re.compile(
    r"(?:"
    r"\bтолько\s+совершеннолетн"
    r"|\bнесовершеннолетн\w*\s+(?:нельзя|не\s+(?:приним|расс|подход))"
    r"|\bдостижение\s+совершеннолетия"
    r")",
    re.IGNORECASE,
)


def make_async_client(
    *,
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | float | None = None,
    follow_redirects: bool = False,
) -> httpx.AsyncClient:
    """Фабрика httpx.AsyncClient с прокси из settings.parser_proxy.

    Если PARSER_PROXY пуст — клиент идёт напрямую. Если задан — все запросы
    парсера пойдут через указанный HTTP/HTTPS/SOCKS5 прокси.
    SOCKS5 требует ``socksio`` в requirements.
    """
    kwargs: dict[str, Any] = {
        "timeout": timeout if timeout is not None else httpx.Timeout(20.0, connect=10.0),
        "headers": headers or {"Accept-Language": "ru,en;q=0.8"},
        "follow_redirects": follow_redirects,
    }
    proxy = (settings.parser_proxy or "").strip()
    if proxy:
        kwargs["proxy"] = proxy
        logger.info("parsers: using proxy %s", _mask_proxy(proxy))
    return httpx.AsyncClient(**kwargs)


def _mask_proxy(url: str) -> str:
    """Маскирует логин/пароль в URL прокси для логов."""
    try:
        # http://user:pass@host:port → http://***@host:port
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            _, host = rest.split("@", 1)
            return f"{scheme}://***@{host}"
        return url
    except ValueError:
        return "***"


class BaseParser(abc.ABC):
    """Базовый класс источника. Каждый источник реализует ``fetch()``."""

    source: str = "base"

    def __init__(self, client: httpx.AsyncClient | None = None, **opts):
        self.client = client or make_async_client()
        self.opts = opts

    async def aclose(self) -> None:
        await self.client.aclose()

    @abc.abstractmethod
    async def fetch(self, *, limit: int = 50) -> list[VacancyDTO]:  # pragma: no cover
        ...

    # ---- helpers ----------------------------------------------------------------

    @staticmethod
    def detect_min_age(text: str) -> int:
        """Эвристика по тексту вакансии: 14 / 16 / 18.

        Стратегия:
        1. Собираем все возрастные кандидаты из текста (regex'ы + текстовые
           подсказки про «школьник»/«совершеннолетним»).
        2. Берём **минимум** найденных — если в вакансии и «от 14 лет», и
           «от 18 лет», то 14+ доступнее, выбираем его.
        3. Нормализуем к 14 / 16 / 18 (диапазон, который мы поддерживаем).
        4. Если ничего не нашли — 16 (нейтральный дефолт).
        """
        if not text:
            return 16

        candidates: list[int] = []

        for pat in _AGE_NUMBER_PATTERNS:
            for m in pat.finditer(text):
                try:
                    age = int(m.group(1))
                except (TypeError, ValueError):
                    continue
                # Игнорируем числа вне человеческого диапазона возраста.
                if 14 <= age <= 60:
                    candidates.append(age)

        if _RE_TEEN_TEXT_HINTS.search(text):
            candidates.append(14)

        if _RE_ADULT_TEXT_HINTS.search(text):
            candidates.append(18)

        if not candidates:
            return 16

        min_age = min(candidates)

        # Нормализуем в наши три бакета.
        if min_age <= 15:
            return 14
        if min_age <= 17:
            return 16
        return 18

    @staticmethod
    def normalize_format(remote: bool | None, schedule: str | None) -> str:
        if remote:
            return "online"
        if schedule and "удал" in schedule.lower():
            return "online"
        return "offline"
