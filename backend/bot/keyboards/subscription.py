"""Клавиатура prompt-а подписки на канал."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def kb_subscribe(channel: str) -> InlineKeyboardMarkup:
    handle = (channel or "").lstrip("@")
    url = f"https://t.me/{handle}" if handle else "https://t.me/grindywork"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📣 Подписаться", url=url)],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="sub:check")],
        ]
    )
