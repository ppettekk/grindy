"""Recheck-handler для кнопки «Я подписался»."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import settings
from app.services.subscription import is_subscribed

from ..keyboards.subscription import kb_subscribe

router = Router(name="subscription")


@router.callback_query(F.data == "sub:check")
async def cb_recheck(c: CallbackQuery) -> None:
    channel = (settings.require_channel or "").strip()
    if not channel:
        await c.answer()
        return

    bot = c.bot
    if bot is None:
        await c.answer()
        return

    if await is_subscribed(bot, c.from_user.id, channel):
        # Удаляем prompt и говорим спасибо.
        try:
            if c.message:
                await c.message.delete()
        except Exception:  # noqa: BLE001
            pass
        if c.message:
            await c.message.answer(
                "🎉 Спасибо за подписку!\n"
                "Теперь жми /start или /search — лента уже ждёт."
            )
        await c.answer()
    else:
        # Не подписан — обновим клавиатуру и поясним.
        try:
            if c.message:
                await c.message.edit_reply_markup(reply_markup=kb_subscribe(channel))
        except Exception:  # noqa: BLE001
            pass
        await c.answer(
            "Не вижу подписки. Подпишись и нажми кнопку ещё раз.",
            show_alert=True,
        )
