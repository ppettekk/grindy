from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class SavedVacancy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_vacancies"
    __table_args__ = (
        UniqueConstraint("user_id", "vacancy_id", name="uq_saved_user_vacancy"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("vacancies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
