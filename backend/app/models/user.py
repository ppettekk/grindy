from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(120))

    city: Mapped[str | None] = mapped_column(String(120))
    age_filter: Mapped[int] = mapped_column(Integer, default=16)  # 14 / 16 / 18
    format_filter: Mapped[str] = mapped_column(String(16), default="all")  # all / online / offline
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)

    notifications_morning: Mapped[bool] = mapped_column(Boolean, default=True)
    notifications_evening: Mapped[bool] = mapped_column(Boolean, default=True)
    # Push новых вакансий в реальном времени (между утром и вечером).
    notifications_realtime: Mapped[bool] = mapped_column(Boolean, default=False)
    # Курсор для дедупа push-уведомлений: время самой свежей отправленной.
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
