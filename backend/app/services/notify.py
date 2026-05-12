"""Realtime push новых вакансий пользователям с notifications_realtime=True.

Запускается из scheduler каждые ``NOTIFY_INTERVAL_MIN`` минут.
Дедуп — через User.last_notified_at: показываем только то, что появилось
после последней отправки конкретному юзеру.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import SessionLocal
from ..models import User
from .digest import format_card, pick_for_user

logger = logging.getLogger(__name__)


async def _eligible_users(session: AsyncSession) -> list[User]:
    stmt = (
        select(User)
        .where(
            User.notifications_realtime.is_(True),
            User.onboarded.is_(True),
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def send_realtime(*, bot=None, max_per_user: int = 3) -> int:
    """Шлёт каждому подходящему юзеру до ``max_per_user`` новых вакансий.

    Возвращает количество получателей, которым реально что-то ушло.
    """
    own_bot = False
    if bot is None:
        if not settings.bot_token:
            return 0
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        from bot.main import build_session  # type: ignore

        bot = Bot(
            token=settings.bot_token,
            session=build_session(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        own_bot = True

    sent_users = 0
    now = datetime.now(UTC)

    try:
        async with SessionLocal() as session:
            users = await _eligible_users(session)
            for user in users:
                # Берём то, что появилось после последней пуш-отправки.
                # Если last_notified_at не задан - считаем 24 часа назад.
                since = user.last_notified_at or (now - timedelta(hours=24))
                vacancies = await pick_for_user(
                    session, user, limit=max_per_user, since=since
                )
                if not vacancies:
                    continue

                header = (
                    "🔔 <b>Новые вакансии под твои фильтры</b>\n"
                    f"<i>{len(vacancies)} свеж{_plural(len(vacancies))}</i>"
                )
                cards = "\n\n———\n\n".join(format_card(v) for v in vacancies)
                text = f"{header}\n\n{cards}"

                try:
                    await bot.send_message(
                        user.telegram_id, text, disable_web_page_preview=True
                    )
                    sent_users += 1
                    user.last_notified_at = now
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "realtime push failed for tg=%s: %s",
                        user.telegram_id,
                        e,
                    )
            await session.commit()
    finally:
        if own_bot:
            await bot.session.close()

    logger.info("realtime push: %d users notified", sent_users)
    return sent_users


def _plural(n: int) -> str:
    a = abs(n) % 100
    b = a % 10
    if 10 < a < 20:
        return "их"
    if 1 < b < 5:
        return "ие"
    if b == 1:
        return "ая"
    return "их"
