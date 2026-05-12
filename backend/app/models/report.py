from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class VacancyReport(Base, UUIDMixin, TimestampMixin):
    """Жалобы пользователей на вакансию."""

    __tablename__ = "vacancy_reports"

    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("vacancies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(Text)
