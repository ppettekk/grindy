from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin
from .employer import Employer
from .vacancy import VacancyFormat


class DirectVacancy(Base, UUIDMixin, TimestampMixin):
    """Вакансии, размещённые работодателями напрямую (не парсинг)."""

    __tablename__ = "direct_vacancies"
    __table_args__ = (
        Index("ix_direct_vacancy_city", "city"),
        Index("ix_direct_vacancy_format", "format"),
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("employers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    salary_unit: Mapped[str | None] = mapped_column(String(32), default="/мес")
    city: Mapped[str | None] = mapped_column(String(120))
    format: Mapped[VacancyFormat] = mapped_column(
        Enum(VacancyFormat, name="direct_vacancy_format"), default=VacancyFormat.offline
    )
    category: Mapped[str | None] = mapped_column(String(120))
    min_age: Mapped[int] = mapped_column(Integer, default=14)
    contact: Mapped[str | None] = mapped_column(Text)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    employer: Mapped[Employer] = relationship("Employer", lazy="joined")
