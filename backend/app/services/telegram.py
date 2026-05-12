"""Singleton Bot для FastAPI-стороны.

Бэкенд и бот живут в разных контейнерах docker-compose, поэтому каждый
держит свой Bot. Здесь — ленивый синглтон с поддержкой того же прокси,
что и в `bot/main.py::build_session`.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from ..config import settings

logger = logging.getLogger(__name__)


def _build_session() -> AiohttpSession:
    if not settings.bot_proxy:
        return AiohttpSession()
    if settings.bot_proxy.startswith("socks"):
        from aiohttp_socks import ProxyConnector

        connector = ProxyConnector.from_url(settings.bot_proxy)
        session = AiohttpSession()
        session._connector_init = {"connector": connector}  # type: ignore[attr-defined]
        return session
    return AiohttpSession(proxy=settings.bot_proxy)


@lru_cache
def get_bot() -> Bot | None:
    """Возвращает синглтон Bot, или None если токен не задан."""
    if not settings.bot_token:
        return None
    return Bot(
        token=settings.bot_token,
        session=_build_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
