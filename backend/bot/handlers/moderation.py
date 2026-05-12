"""Inline-callback'и модерации в админ-уведомлениях.

Когда админ нажимает «Восстановить»/«Бан» под уведомлением об автоскрытии,
прилетает callback вида ``mod:restore:<vacancy_id>`` или ``mod:ban:<vacancy_id>``.
"""
from __future__ import annotations

import logging
import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import settings
from app.db import SessionLocal
from app.services.moderation_actions import ban_vacancy, restore_vacancy

logger = logging.getLogger(__name__)
router = Router(name="moderation")


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_tg_ids


@router.callback_query(F.data.startswith("mod:"))
async def cb_moderation(c: CallbackQuery) -> None:
    if not c.from_user or not _is_admin(c.from_user.id):
        await c.answer("Только для админов", show_alert=True)
        return

    parts = (c.data or "").split(":", 2)
    if len(parts) != 3:
        await c.answer("Битый callback", show_alert=True)
        return

    _, action, vid_str = parts
    try:
        vid = uuid.UUID(vid_str)
    except ValueError:
        await c.answer("Кривой UUID", show_alert=True)
        return

    async with SessionLocal() as session:
        if action == "restore":
            ok = await restore_vacancy(session, vid)
            new_text = "✅ Восстановлено."
        elif action == "ban":
            ok = await ban_vacancy(session, vid)
            new_text = "🗑 Забанено навсегда."
        else:
            await c.answer("Неизвестное действие", show_alert=True)
            return

    if not ok:
        await c.answer("Вакансия не найдена", show_alert=True)
        return

    # Обновим сообщение, чтобы было видно итог.
    if c.message:
        try:
            old = c.message.html_text or c.message.text or ""
            await c.message.edit_text(old + f"\n\n<i>{new_text}</i>")
        except Exception as e:  # noqa: BLE001
            logger.debug("edit_text failed: %s", e)
    await c.answer(new_text)
