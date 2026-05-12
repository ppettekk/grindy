from .avito import AvitoParser
from .base import BaseParser
from .hh import HhParser
from .rabota import RabotaParser
from .superjob import SuperJobParser
from .trudvsem import TrudvsemParser

# Активные источники для регулярного ingest.
# HhParser и AvitoParser выключены: IP yeezyhost в банлисте DDoS-Guard/anti-bot.
# Включить обратно, как только заведём резидентный/мобильный PARSER_PROXY.
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
