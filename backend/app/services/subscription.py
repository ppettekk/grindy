"""Проверка подписки пользователя на канал.

На старте бота и для использования WebApp требуется подписка на
`@grindywork`. Канал задаётся в настройках через `REQUIRE_CHANNEL`.
Если переменная пустая — фича выключена, всё пропускается.

ВАЖНО: бот должен быть админом канала (или хотя бы участником
публичного канала), иначе Bot API вернёт 400.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError

from ..config import settings

logger = logging.getLogger(__name__)


_OK_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
}


async def is_subscribed(bot: Bot, user_id: int, channel: str | None = None) -> bool:
    """Подписан ли пользователь на канал.

    - Если канал не задан → True (фича выключена).
    - При любых ошибках API (бот не в канале, неверный chat_id и т.п.) → False.
    """
    ch = (channel or settings.require_channel or "").strip()
    if not ch:
        return True
    try:
        m = await bot.get_chat_member(ch, user_id)
    except TelegramAPIError as e:
        logger.warning("get_chat_member(%s, %d) failed: %s", ch, user_id, e)
        return False
    except Exception as e:  # noqa: BLE001
        logger.warning("get_chat_member unexpected: %s", e)
        return False
    return m.status in _OK_STATUSES
