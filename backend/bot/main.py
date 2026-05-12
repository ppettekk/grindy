"""Точка входа Telegram-бота (aiogram 3.x)."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.db import init_db

from .handlers import setup_handlers
from .middlewares.subscription import SubscriptionMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("grindy.bot")


# Sentry init - опциональный.
if settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_env,
            traces_sample_rate=0.1,
            send_default_pii=False,
            integrations=[AsyncioIntegration()],
        )
        logger.info("Sentry initialised in bot (env=%s)", settings.sentry_env)
    except ImportError:
        logger.warning("SENTRY_DSN задан, но sentry-sdk не установлен")
    except Exception as e:  # noqa: BLE001
        logger.warning("Sentry init failed: %s", e)


def build_session() -> AiohttpSession:
    """Создаёт aiogram-сессию с опциональным прокси (HTTP/SOCKS5)."""
    if not settings.bot_proxy:
        return AiohttpSession()
    if settings.bot_proxy.startswith("socks"):
        from aiohttp_socks import ProxyConnector

        connector = ProxyConnector.from_url(settings.bot_proxy)
        session = AiohttpSession()
        session._connector_init = {"connector": connector}  # type: ignore[attr-defined]
        return session
    return AiohttpSession(proxy=settings.bot_proxy)


async def main() -> None:
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN не задан в .env")

    await init_db()

    bot = Bot(
        token=settings.bot_token,
        session=build_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    sub_mw = SubscriptionMiddleware()
    dp.message.middleware(sub_mw)
    dp.callback_query.middleware(sub_mw)
    setup_handlers(dp)

    logger.info(
        "Grindy bot starting%s…",
        f" (через прокси {settings.bot_proxy})" if settings.bot_proxy else "",
    )
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
