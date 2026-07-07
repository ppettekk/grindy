"""Entry point для avito-контейнера.

Отдельный процесс: периодически парсит Avito через Playwright и пишет
вакансии в общую БД (тот же DATABASE_URL, что и backend).

Вынесен в отдельный контейнер, потому что Playwright + Chromium тяжёлые
(~500МБ образ, сотни МБ RAM) — не хотим тащить их в backend/bot.

init_db здесь НЕ вызывается: схему и миграции накатывает backend при
старте. avito-worker только пишет данные.
"""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.db import SessionLocal
from app.parsers.avito import AvitoParser
from app.services.ingest import run_ingest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("grindy.avito")


async def job_avito() -> None:
    logger.info("avito-worker: starting ingest")
    try:
        async with SessionLocal() as session:
            stats = await run_ingest(session, parsers=[AvitoParser])
        logger.info("avito-worker: done %s", stats)
    except Exception as e:  # noqa: BLE001
        logger.exception("avito-worker: ingest failed: %s", e)


async def main() -> None:
    if not settings.avito_enabled:
        logger.info("AVITO_ENABLED=false — воркер простаивает.")
        # Держим процесс живым, чтобы контейнер не рестартился в цикле.
        while True:
            await asyncio.sleep(3600)

    # Небольшая задержка на старте: даём backend поднять БД/миграции.
    await asyncio.sleep(30)
    await job_avito()

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        job_avito,
        IntervalTrigger(minutes=settings.avito_interval_min),
        id="avito_ingest",
        replace_existing=True,
        max_instances=1,  # не запускаем второй парсинг, пока идёт первый
    )
    scheduler.start()
    logger.info(
        "avito-worker started: interval %s min", settings.avito_interval_min
    )

    # Бесконечный сон — scheduler работает в фоне.
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
