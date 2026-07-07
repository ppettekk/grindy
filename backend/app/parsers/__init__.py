from .avito import AvitoParser
from .base import BaseParser
from .hh import HhParser
from .rabota import RabotaParser
from .superjob import SuperJobParser
from .trudvsem import TrudvsemParser

# Активные источники для регулярного ingest.
# Работают: SuperJob (API), Rabota + Trudvsem (через мобильный PARSER_PROXY).
# HhParser выключен: HH DDoS-Guard блокирует даже мобильные IP (403 на всё) —
# нужен Playwright + cookie-сессия, отдельная задача.
# AvitoParser выключен: своя JS-проверка DataDome.
# Код обоих сохранён, фильтр label=accept_kids в hh.py готов — включить,
# когда появится способ обходить DDoS-Guard.
ALL_PARSERS: list[type[BaseParser]] = [
    SuperJobParser,
    RabotaParser,
    TrudvsemParser,
]

__all__ = [
    "BaseParser",
    "HhParser",
    "SuperJobParser",
    "AvitoParser",
    "RabotaParser",
    "TrudvsemParser",
    "ALL_PARSERS",
]
