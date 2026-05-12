"""Действия модерации: скрытие/восстановление вакансий + уведомления админам."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Vacancy, VacancyReport
from .telegram import get_bot

logger = logging.getLogger(__name__)


async def count_distinct_reporters(session: AsyncSession, vacancy_id: uuid.UUID) -> int:
    """Сколько разных юзеров пожаловались на эту вакансию."""
    stmt = (
        select(func.count(func.distinct(VacancyReport.user_id)))
        .where(
            VacancyReport.vacancy_id == vacancy_id,
            VacancyReport.user_id.isnot(None),
        )
    )
    res = await session.execute(stmt)
    return int(res.scalar_one() or 0)


async def maybe_autohide(session: AsyncSession, vacancy_id: uuid.UUID) -> bool:
    """Если жалоб >= порога — скрыть вакансию и уведомить админов.

    Возвращает True если вакансия только что была скрыта (action triggered).
    """
    v = await session.get(Vacancy, vacancy_id)
    if v is None or v.is_hidden:
        return False

    cnt = await count_distinct_reporters(session, vacancy_id)
    if cnt < settings.report_autohide_threshold:
        return False

    v.is_hidden = True
    v.hidden_reason = f"auto: {cnt} жалоб от пользователей"
    await session.commit()
    await session.refresh(v)

    await notify_admins_hidden(v, cnt)
    return True


async def notify_admins_hidden(v: Vacancy, reports_count: int) -> None:
    """Шлёт админам уведомление с inline-кнопками."""
    admins = settings.admin_tg_ids
    if not admins:
        logger.info("autohide: ADMIN_TG_IDS пуст, никого не уведомляем")
        return

    bot = get_bot()
    if bot is None:
        logger.warning("autohide: BOT_TOKEN не задан, не могу уведомить админов")
        return

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    title = (v.title or "")[:140]
    company = v.company or "—"
    text = (
        f"🚨 <b>Авто-скрытие вакансии</b>\n\n"
        f"<b>{title}</b>\n"
        f"Компания: {company}\n"
        f"Город: {v.city or '—'}\n"
        f"Источник: {v.source.value}\n\n"
        f"Жалоб: <b>{reports_count}</b>\n"
        f"<a href='{v.url}'>Открыть оригинал</a>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Восстановить", callback_data=f"mod:restore:{v.id}"),
                InlineKeyboardButton(text="🗑 Бан навсегда", callback_data=f"mod:ban:{v.id}"),
            ]
        ]
    )
    for admin_id in admins:
        try:
            await bot.send_message(
                admin_id, text, reply_markup=kb, disable_web_page_preview=True
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("autohide: failed to notify admin %d: %s", admin_id, e)


async def restore_vacancy(session: AsyncSession, vacancy_id: uuid.UUID) -> bool:
    v = await session.get(Vacancy, vacancy_id)
    if v is None:
        return False
    v.is_hidden = False
    v.hidden_reason = None
    await session.commit()
    return True


async def ban_vacancy(session: AsyncSession, vacancy_id: uuid.UUID) -> bool:
    """Помечает как is_spam=True (постоянный бан) + is_hidden=True."""
    v = await session.get(Vacancy, vacancy_id)
    if v is None:
        return False
    v.is_hidden = True
    v.is_spam = True
    v.hidden_reason = "admin: permanent ban"
    await session.commit()
    return True
