"""APScheduler-jobs: парсинг, дайджесты, push новых вакансий."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from ..db import SessionLocal
from ..services.digest import send_digest
from ..services.ingest import run_ingest
from ..services.notify import send_realtime

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def job_ingest() -> None:
    logger.info("scheduler: starting ingest")
    async with SessionLocal() as session:
        stats = await run_ingest(session)
    logger.info("scheduler: ingest done %s", stats)


async def job_morning_digest() -> None:
    await send_digest("morning")


async def job_evening_digest() -> None:
    await send_digest("evening")


async def job_realtime_notify() -> None:
    await send_realtime()


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    _scheduler.add_job(
        job_ingest,
        IntervalTrigger(minutes=settings.parse_interval_min),
        id="ingest",
        replace_existing=True,
    )

    _scheduler.add_job(
        job_morning_digest,
        CronTrigger.from_crontab(settings.digest_morning, timezone="Europe/Moscow"),
        id="digest_morning",
        replace_existing=True,
    )
    _scheduler.add_job(
        job_evening_digest,
        CronTrigger.from_crontab(settings.digest_evening, timezone="Europe/Moscow"),
        id="digest_evening",
        replace_existing=True,
    )

    # Realtime push: каждые NOTIFY_INTERVAL_MIN минут проверяем, не появилось
    # ли свежих вакансий для юзеров, у которых включён realtime.
    _scheduler.add_job(
        job_realtime_notify,
        IntervalTrigger(minutes=settings.notify_interval_min),
        id="realtime_notify",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "scheduler started: ingest %s min, realtime %s min, digests %s / %s",
        settings.parse_interval_min,
        settings.notify_interval_min,
        settings.digest_morning,
        settings.digest_evening,
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
