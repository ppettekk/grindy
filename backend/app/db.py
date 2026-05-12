"""Async SQLAlchemy engine и session factory."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Лёгкие idempotent ALTER-миграции для существующей БД.
# Запускаются при старте; для свежей БД ничего не делают (колонки уже создаются через create_all).
PG_MIGRATIONS = [
    # ── Новые значения enum'а источников ──────────────────────────
    "ALTER TYPE vacancy_source ADD VALUE IF NOT EXISTS 'trudvsem'",
    # ── LLM-классификация ─────────────────────────────────────────
    "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS llm_classified BOOLEAN NOT NULL DEFAULT FALSE",
    # ── Модерация / скрытие ────────────────────────────────────────
    "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS hidden_reason TEXT",
    "CREATE INDEX IF NOT EXISTS ix_vacancy_is_hidden ON vacancies(is_hidden)",
    # ── Уведомления юзера ──────────────────────────────────────────
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_realtime BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ",
    # ── Полнотекстовый поиск ───────────────────────────────────────
    "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS search_vector tsvector",
    "CREATE INDEX IF NOT EXISTS ix_vacancy_search_vector ON vacancies USING GIN(search_vector)",
    # Триггер: обновляет tsvector на INSERT / UPDATE
    """
    CREATE OR REPLACE FUNCTION grindy_vacancy_search_update() RETURNS trigger AS $$
    BEGIN
        NEW.search_vector :=
            setweight(to_tsvector('russian', coalesce(NEW.title, '')), 'A') ||
            setweight(to_tsvector('russian', coalesce(NEW.company, '')), 'B') ||
            setweight(to_tsvector('russian', coalesce(NEW.category, '')), 'B') ||
            setweight(to_tsvector('russian', coalesce(NEW.description, '')), 'C');
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS grindy_vacancy_search_trg ON vacancies",
    """
    CREATE TRIGGER grindy_vacancy_search_trg
    BEFORE INSERT OR UPDATE ON vacancies
    FOR EACH ROW EXECUTE FUNCTION grindy_vacancy_search_update()
    """,
    # Backfill: триггер прогонит существующие строки.
    "UPDATE vacancies SET title = title WHERE search_vector IS NULL",
]


async def _run_light_migrations() -> None:
    """Применяет ALTER TABLE'ы поверх существующей БД (только для PG)."""
    if "postgres" not in settings.database_url:
        return

    # ALTER TYPE ... ADD VALUE требует autocommit (вне транзакции).
    # Выделяем их в отдельный пробег.
    def _is_enum_add(sql: str) -> bool:
        s = sql.upper()
        return "ALTER TYPE" in s and "ADD VALUE" in s

    enum_migrations = [m for m in PG_MIGRATIONS if _is_enum_add(m)]
    other_migrations = [m for m in PG_MIGRATIONS if not _is_enum_add(m)]

    for sql in enum_migrations:
        try:
            async with engine.connect() as conn:
                await conn.execution_options(isolation_level="AUTOCOMMIT")
                await conn.execute(text(sql))
        except Exception as e:  # noqa: BLE001
            logger.warning("enum migration failed: %s ; sql=%r", e, sql[:80])

    async with engine.begin() as conn:
        for sql in other_migrations:
            try:
                await conn.execute(text(sql))
            except Exception as e:  # noqa: BLE001
                logger.warning("light migration failed: %s ; sql=%r", e, sql[:80])


async def init_db() -> None:
    """Создаёт таблицы и применяет лёгкие миграции."""
    from .models import Base  # noqa: WPS433

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _run_light_migrations()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
