"""Онбординг (FSM): city → age → format → categories → notifications → done."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.db import SessionLocal
from app.models import User

from ..keyboards.onboarding import (
    CATEGORIES,
    kb_age,
    kb_categories,
    kb_cities,
    kb_format,
    kb_notifications,
    kb_open_webapp,
    kb_start,
)

logger = logging.getLogger(__name__)
router = Router(name="start")


class Onboarding(StatesGroup):
    city = State()
    city_text = State()  # ручной ввод города
    age = State()
    fmt = State()
    categories = State()
    notifications = State()


HELLO = (
    "<b>grindy.</b>\n"
    "Подработка для подростков 14–18 лет.\n\n"
    "Собираю свежие вакансии с hh, Авито, SuperJob и Работа.ру. "
    "Спам и MLM фильтрую через AI. Утром в 9:00 и вечером в 19:00 присылаю топ-5 под твои фильтры.\n\n"
    "Поехали — настроим за 30 секунд."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _ensure_user(message)
    await message.answer(HELLO, reply_markup=kb_start())


@router.callback_query(F.data == "onb:go")
async def onb_go(c: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Onboarding.city)
    await c.message.edit_text(  # type: ignore[union-attr]
        "🌆 <b>Где ищем работу?</b>\nВыбери город или введи свой.",
        reply_markup=kb_cities(),
    )
    await c.answer()


@router.callback_query(F.data.startswith("onb:city:"))
async def onb_city(c: CallbackQuery, state: FSMContext) -> None:
    value = (c.data or "").removeprefix("onb:city:")
    if value == "other":
        await state.set_state(Onboarding.city_text)
        await c.message.edit_text(  # type: ignore[union-attr]
            "Напиши название города одним сообщением:"
        )
        await c.answer()
        return

    await state.update_data(city=value)
    await state.set_state(Onboarding.age)
    await c.message.edit_text(  # type: ignore[union-attr]
        f"Город: <b>{value}</b>\n\n👤 <b>Сколько тебе лет?</b>",
        reply_markup=kb_age(),
    )
    await c.answer()


@router.message(Onboarding.city_text)
async def onb_city_text(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()[:80] or "Москва"
    await state.update_data(city=city)
    await state.set_state(Onboarding.age)
    await message.answer(
        f"Город: <b>{city}</b>\n\n👤 <b>Сколько тебе лет?</b>",
        reply_markup=kb_age(),
    )


@router.callback_query(F.data.startswith("onb:age:"))
async def onb_age(c: CallbackQuery, state: FSMContext) -> None:
    age = int((c.data or "").removeprefix("onb:age:"))
    await state.update_data(age=age)
    await state.set_state(Onboarding.fmt)
    await c.message.edit_text(  # type: ignore[union-attr]
        f"Возраст: <b>{age}+</b>\n\n💻 <b>Формат работы?</b>",
        reply_markup=kb_format(),
    )
    await c.answer()


@router.callback_query(F.data.startswith("onb:fmt:"))
async def onb_fmt(c: CallbackQuery, state: FSMContext) -> None:
    fmt = (c.data or "").removeprefix("onb:fmt:")
    await state.update_data(fmt=fmt, picked=set())
    await state.set_state(Onboarding.categories)
    await c.message.edit_text(  # type: ignore[union-attr]
        "🎯 <b>Что интересно?</b>\nМожно выбрать несколько.",
        reply_markup=kb_categories(set()),
    )
    await c.answer()


@router.callback_query(F.data.startswith("onb:cat:"))
async def onb_cat(c: CallbackQuery, state: FSMContext) -> None:
    raw = (c.data or "").removeprefix("onb:cat:")
    data = await state.get_data()
    picked: set[str] = set(data.get("picked", set()))

    if raw == "done":
        await state.update_data(picked=list(picked))
        await state.set_state(Onboarding.notifications)
        await c.message.edit_text(  # type: ignore[union-attr]
            f"Категорий выбрано: <b>{len(picked) or 'все'}</b>\n\n"
            "🔔 <b>Включить пуши?</b>\n"
            "В 9:00 и 19:00 буду присылать топ-5 свежих вакансий под твои фильтры.",
            reply_markup=kb_notifications(),
        )
        await c.answer()
        return

    if raw not in CATEGORIES:
        await c.answer("Неизвестная категория")
        return

    if raw in picked:
        picked.remove(raw)
    else:
        picked.add(raw)
    await state.update_data(picked=list(picked))
    await c.message.edit_reply_markup(reply_markup=kb_categories(picked))  # type: ignore[union-attr]
    await c.answer()


@router.callback_query(F.data.startswith("onb:notif:"))
async def onb_notif(c: CallbackQuery, state: FSMContext) -> None:
    notif_on = (c.data or "").removeprefix("onb:notif:") == "on"
    data = await state.get_data()

    user = await _save_user(
        telegram_id=c.from_user.id,
        username=c.from_user.username,
        first_name=c.from_user.first_name,
        city=data.get("city"),
        age=data.get("age", 16),
        fmt=data.get("fmt", "all"),
        categories=list(data.get("picked", []) or []),
        notif=notif_on,
    )

    await state.clear()
    await c.message.edit_text(  # type: ignore[union-attr]
        "🎉 <b>Готово!</b>\n"
        f"Город: <b>{user.city}</b> · {user.age_filter}+ · {_fmt_label(user.format_filter)}\n"
        f"Уведомления: <b>{'включены' if notif_on else 'выключены'}</b>\n\n"
        "Открывай Grindy — лента уже ждёт.",
        reply_markup=kb_open_webapp(),
    )
    await c.answer()


def _fmt_label(fmt: str) -> str:
    return {"online": "онлайн", "offline": "офлайн", "all": "любой формат"}.get(fmt, fmt)


async def _ensure_user(message: Message) -> None:
    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = res.scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                )
            )
            await session.commit()


async def _save_user(
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    city: str | None,
    age: int,
    fmt: str,
    categories: list[str],
    notif: bool,
) -> User:
    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id)
            session.add(user)

        user.username = username
        user.first_name = first_name
        user.city = city or user.city
        user.age_filter = age
        user.format_filter = fmt
        user.categories = categories
        user.notifications_morning = notif
        user.notifications_evening = notif
        user.onboarded = True

        await session.commit()
        await session.refresh(user)
        return user
