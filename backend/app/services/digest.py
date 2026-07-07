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


def _user_filters_stmt(user: User):
    """Базовый SELECT с фильтрами юзера (без временного окна)."""
    stmt = select(Vacancy).where(
        Vacancy.is_spam.is_(False), Vacancy.is_hidden.is_(False)
    )
    if user.city:
        city_aliases = aliases_for(user.city) or [user.city]
        stmt = stmt.where(
            or_(
                *(Vacancy.city.ilike(f"%{a}%") for a in city_aliases),
                Vacancy.format == VacancyFormat.online,
            )
        )
    if user.age_filter == 14:
        stmt = stmt.where(Vacancy.min_age <= 14)
    # 16/18 — показываем всё, фронт пометит 18+ значком.
    if user.format_filter and user.format_filter != "all":
        stmt = stmt.where(Vacancy.format == VacancyFormat(user.format_filter))
    if user.categories:
        stmt = stmt.where(
            or_(Vacancy.category.in_(user.categories), Vacancy.category.is_(None))
        )
    return stmt


async def pick_for_user(
    session: AsyncSession,
    user: User,
    *,
    limit: int = 5,
    since: datetime | None = None,
) -> list[Vacancy]:
    """Подбирает top-N вакансий с fallback-расширением окна.

    Если за переданный ``since`` подходящего нет — расширяем 7 дней,
    потом «без ограничения по времени». Это нужно для дайджестов:
    если за ночь не было новых под фильтры юзера, всё равно показать
    топ-свежее, а не пустоту.
    """
    base = _user_filters_stmt(user)
    order = base.order_by(
        Vacancy.is_featured.desc(), Vacancy.created_at.desc()
    )

    # 1) Точное окно (если задано)
    if since:
        stmt = order.where(Vacancy.created_at >= since).limit(limit)
        rows = list((await session.execute(stmt)).scalars().all())
        if rows:
            return rows

    # 2) Fallback: последние 7 дней
    week_ago = datetime.now(UTC) - timedelta(days=7)
    stmt = order.where(Vacancy.created_at >= week_ago).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())
    if rows:
        logger.info(
            "pick_for_user tg=%s: fallback to 7d (no fresh in window)",
            user.telegram_id,
        )
        return rows

    # 3) Последний fallback — без ограничения по времени
    rows = list(
        (await session.execute(order.limit(limit))).scalars().all()
    )
    if rows:
        logger.info(
            "pick_for_user tg=%s: fallback to all-time", user.telegram_id
        )
    return rows


def format_card(v: Vacancy) -> str:
    """HTML-форматирование карточки вакансии для Telegram.

    Кнопка «Открыть в Grindy» больше не в тексте — её добавляет вызывающий
    код через inline keyboard (см. build_vacancies_keyboard). Здесь только
    текст с ссылкой на источник.
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

    return (
        f"<b>{_esc(v.title)}</b>\n"
        f"<i>{_esc(company)}</i>\n"
        f"💰 {_esc(salary)}\n"
        f"📍 {_esc(city)} · {_esc(fmt)} · {v.min_age}+\n"
        f'<a href="{v.url}">источник →</a>'
    )


def vacancy_webapp_url(v: Vacancy) -> str:
    """URL для open-in-webapp inline-кнопки. Фронт читает ?v=<hex> и
    сразу открывает DetailScreen этой вакансии."""
    base = (settings.webapp_url or "").rstrip("/")
    return f"{base}/?v={v.id.hex}"


def build_vacancies_keyboard(vacancies: list[Vacancy]) -> dict:
    """Inline-клавиатура с кнопками «1», «2», «3»… по числу вакансий.

    Каждая кнопка — WebApp deep link (через URL query). Это работает
    надёжнее, чем `t.me/<bot>/<short_name>?startapp=...`, потому что не
    зависит от того, заведено ли у бота Mini App с тем же short_name.
    Возвращаем словарь, который aiogram сам конвертирует в reply_markup.
    """
    return {
        "inline_keyboard": [
            [
                {
                    "text": f"{i + 1} · открыть",
                    "web_app": {"url": vacancy_webapp_url(v)},
                }
                for i, v in enumerate(vacancies)
            ]
        ]
    }


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
                    await bot.send_message(
                        user.telegram_id,
                        text,
                        disable_web_page_preview=True,
                        reply_markup=build_vacancies_keyboard(vacancies),
                    )
                    sent += 1
                except Exception as e:  # noqa: BLE001
                    logger.warning("send_digest failed for tg=%s: %s", user.telegram_id, e)
    finally:
        if own_bot:
            await bot.session.close()

    logger.info("digest %s sent to %s users", kind, sent)
    return sent
