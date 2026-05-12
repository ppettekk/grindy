"""FastAPI зависимости."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import SessionLocal
from ..services.tg_auth import verify_init_data


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def current_telegram_user(
    x_telegram_init_data: str | None = Header(default=None),
) -> dict | None:
    """Извлекает (и валидирует) Telegram WebApp пользователя по заголовку."""
    if not x_telegram_init_data:
        return None
    return verify_init_data(x_telegram_init_data)
