"""/settings — переключение пушей и сводка по фильтрам."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from app.db import SessionLocal
from app.models import User

router = Router(name="settings")


def kb_settings(user: User) -> InlineKeyboardMarkup:
    morning = "🔔" if user.notifications_morning else "🔕"
    evening = "🔔" if user.notifications_evening else "🔕"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{morning} Утренняя 9:00", callback_data="set:morning")],
            [InlineKeyboardButton(text=f"{evening} Вечерняя 19:00", callback_data="set:evening")],
        ]
    )


def render(user: User) -> str:
    cats = ", ".join(user.categories) if user.categories else "все"
    return (
        "<b>Настройки</b>\n\n"
        f"Город: <b>{user.city or '—'}</b>\n"
        f"Возраст: <b>{user.age_filter}+</b>\n"
        f"Формат: <b>{user.format_filter}</b>\n"
        f"Категории: <i>{cats}</i>\n\n"
        f"Утренняя подборка: <b>{'вкл' if user.notifications_morning else 'выкл'}</b>\n"
        f"Вечерняя подборка: <b>{'вкл' if user.notifications_evening else 'выкл'}</b>"
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = res.scalar_one_or_none()
        if user is None:
            await message.answer("Сначала пройди /start.")
            return
        await message.answer(render(user), reply_markup=kb_settings(user))


@router.callback_query(F.data.startswith("set:"))
async def toggle_notif(c: CallbackQuery) -> None:
    field = (c.data or "").split(":", 1)[1]
    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.telegram_id == c.from_user.id))
        user = res.scalar_one_or_none()
        if user is None:
            await c.answer("Сначала /start", show_alert=True)
            return
        if field == "morning":
            user.notifications_morning = not user.notifications_morning
        elif field == "evening":
            user.notifications_evening = not user.notifications_evening
        await session.commit()
        await session.refresh(user)
        await c.message.edit_text(render(user), reply_markup=kb_settings(user))  # type: ignore[union-attr]
    await c.answer("Сохранено")
