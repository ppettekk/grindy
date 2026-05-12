"""Middleware: блокирует все handlers, пока пользователь не подпишется на канал.

- Если settings.require_channel пустой - middleware ничего не делает.
- Спец-callback'и пропускаются:
    - "sub:check" — recheck-кнопка.
    - "mod:*"     — модерация для админов.
- Для остальных событий: при отсутствии подписки показываем prompt и
  блокируем дальнейший вызов handler.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import settings
from app.services.subscription import is_subscribed

from ..keyboards.subscription import kb_subscribe

logger = logging.getLogger(__name__)


PROMPT = (
    "📣 Чтобы пользоваться <b>Grindy</b>, подпишись на канал @grindywork.\n\n"
    "Там — свежие подборки вакансий, советы по подработке для подростков "
    "и анонсы новых фишек сервиса.\n\n"
    "Подпишись и нажми <b>«Я подписался»</b>."
)


def _is_passthrough_callback(data: str | None) -> bool:
    if not data:
        return False
    return data == "sub:check" or data.startswith("mod:")


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        channel = (settings.require_channel or "").strip()
        if not channel:
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and _is_passthrough_callback(event.data):
            return await handler(event, data)

        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # Админов тоже пропускаем без проверки подписки.
        if user.id in settings.admin_tg_ids:
            return await handler(event, data)

        bot = data.get("bot")
        if bot is None:
            return await handler(event, data)

        if await is_subscribed(bot, user.id, channel):
            return await handler(event, data)

        kb = kb_subscribe(channel)
        if isinstance(event, Message):
            await event.answer(PROMPT, reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            try:
                if event.message:
                    await event.message.answer(PROMPT, reply_markup=kb)
            except Exception as e:  # noqa: BLE001
                logger.debug("subscription prompt send failed: %s", e)
            await event.answer("Сначала подпишись на @grindywork", show_alert=True)
        return None
