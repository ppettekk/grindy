"""Inline-клавиатуры онбординга."""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from app.config import settings

CITIES = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург"]
CATEGORIES = [
    "Кафе и рестораны",
    "Промоутер",
    "Репетитор и обучение",
    "IT и интернет",
    "Дизайн и творчество",
    "Торговля и продажи",
    "Административная",
    "Доставка",
    "Другое",
]


def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 Поехали", callback_data="onb:go")]]
    )


def kb_cities() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for city in CITIES:
        row.append(InlineKeyboardButton(text=city, callback_data=f"onb:city:{city}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✍️ Другой город", callback_data="onb:city:other")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_age() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="14+", callback_data="onb:age:14"),
                InlineKeyboardButton(text="16+", callback_data="onb:age:16"),
                InlineKeyboardButton(text="18+", callback_data="onb:age:18"),
            ]
        ]
    )


def kb_format() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Онлайн", callback_data="onb:fmt:online"),
                InlineKeyboardButton(text="Офлайн", callback_data="onb:fmt:offline"),
                InlineKeyboardButton(text="И то и то", callback_data="onb:fmt:all"),
            ]
        ]
    )


def kb_categories(picked: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for cat in CATEGORIES:
        marker = "✓ " if cat in picked else ""
        row.append(
            InlineKeyboardButton(text=f"{marker}{cat}", callback_data=f"onb:cat:{cat}")
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="onb:cat:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_notifications() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔔 Включить", callback_data="onb:notif:on"),
                InlineKeyboardButton(text="🔕 Не сейчас", callback_data="onb:notif:off"),
            ]
        ]
    )


def kb_open_webapp() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👀 Открыть Grindy", web_app=WebAppInfo(url=settings.webapp_url))]
        ]
    )
