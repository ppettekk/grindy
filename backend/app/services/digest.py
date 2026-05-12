"""Подбор top-N свежих вакансий для конкретного пользователя
и отправка через бота."""
from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import SessionLocal
from ..models import User, Vacancy, VacancyFormat
from .cities import aliases_for

logger = logging.getLogger(__name__)

DigestKind = Literal["morning", "evening"]


async def pick_for_user(
    session: AsyncSession,
    user: User,
    *,
    limit: int = 5,
    since: datetime | None = None,
) -> list[Vacancy]:
    stmt = select(Vacancy).where(Vacancy.is_spam.is_(False), Vacancy.is_hidden.is_(False))

    if since:
        stmt = stmt.where(Vacancy.created_at >= since)
    if user.city:
        city_aliases = aliases_for(user.city) or [user.city]
        # Город пользователя ИЛИ онлайн-вакансия. Вакансии без города
        # не пускаем — иначе подборка превращается в кашу из разных регионов.
        stmt = stmt.where(
            or_(
                *(Vacancy.city.ilike(f"%{a}%") for a in city_aliases),
                Vacancy.format == VacancyFormat.online,
            )
        )
    if user.age_filter in (14, 16, 18):
        stmt = stmt.where(Vacancy.min_age <= user.age_filter)
    if user.format_filter and user.format_filter != "all":
        stmt = stmt.where(Vacancy.format == VacancyFormat(user.format_filter))
    if user.categories:
        stmt = stmt.where(or_(Vacancy.category.in_(user.categories), Vacancy.category.is_(None)))

    stmt = stmt.order_by(Vacancy.is_featured.desc(), Vacancy.created_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


def format_card(v: Vacancy) -> str:
    """HTML-форматирование карточки вакансии для Telegram.

    Ссылка «Открыть в Grindy» — deep link через startapp, переоткроет
    WebApp и в нём сразу откроется DetailScreen этой вакансии.
    Вторая ссылка «Источник →» ведёт на оригинальный сайт работодателя.
    """
    salary = "не указана"
    if v.salary_from or v.salary_to:
        if v.salary_from and v.salary_to:
            salary = f"{v.salary_from:,}–{v.salary_to:,} ₽".replace(",", " ")
        elif v.salary_from:
            salary = f"от {v.salary_from:,} ₽".replace(",", " ")
        else:
            salary = f"до {v.salary_to:,} ₽".replace(",", " ")
        if v.salary_unit:
            salary += f" {v.salary_unit}"

    company = v.company or ""
    city = v.city or ""
    fmt = v.format.value if hasattr(v.format, "value") else v.format

    deep_link = (
        f"https://t.me/{settings.bot_username}/{settings.webapp_short_name}"
        f"?startapp=v_{v.id.hex}"
    )

    return (
        f"<b>{_esc(v.title)}</b>\n"
        f"<i>{_esc(company)}</i>\n"
        f"💰 {_esc(salary)}\n"
        f"📍 {_esc(city)} · {_esc(fmt)} · {v.min_age}+\n"
        f'<a href="{deep_link}">Открыть в Grindy →</a>'
        f' · <a href="{v.url}">источник</a>'
    )


def _esc(s: str | None) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


async def iter_recipients(session: AsyncSession, kind: DigestKind) -> Iterable[User]:
    flag = User.notifications_morning if kind == "morning" else User.notifications_evening
    stmt = select(User).where(flag.is_(True), User.onboarded.is_(True))
    return (await session.execute(stmt)).scalars().all()


async def send_digest(kind: DigestKind, *, bot=None) -> int:
    """Отправляет утреннюю или вечернюю подборку.

    Если ``bot`` не передан — создаёт временный экземпляр aiogram.Bot.
    Возвращает количество получателей.
    """
    own_bot = False
    if bot is None:
        if not settings.bot_token:
            logger.info("Digest skipped: BOT_TOKEN не задан")
            return 0
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        # Импорт локально, чтобы не тащить bot.* в бэкенд по умолчанию.
        from bot.main import build_session  # type: ignore

        bot = Bot(
            token=settings.bot_token,
            session=build_session(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        own_bot = True

    sent = 0
    now = datetime.now(UTC)
    since = now - timedelta(hours=14 if kind == "morning" else 10)

    try:
        async with SessionLocal() as session:
            users = await iter_recipients(session, kind)
            label = "🌅 Утренняя подборка" if kind == "morning" else "🌆 Вечерняя подборка"

            for user in users:
                vacancies = await pick_for_user(session, user, limit=5, since=since)
                if not vacancies:
                    continue
                header = f"<b>{label}</b>\n<i>топ {len(vacancies)} свежих вакансий по твоим фильтрам</i>"
                cards = "\n\n———\n\n".join(format_card(v) for v in vacancies)
                text = f"{header}\n\n{cards}"

                try:
                    await bot.send_message(user.telegram_id, text, disable_web_page_preview=True)
                    sent += 1
                except Exception as e:  # noqa: BLE001
                    logger.warning("send_digest failed for tg=%s: %s", user.telegram_id, e)
    finally:
        if own_bot:
            await bot.session.close()

    logger.info("digest %s sent to %s users", kind, sent)
    return sent
