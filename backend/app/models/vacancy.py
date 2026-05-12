from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class VacancySource(enum.StrEnum):
    hh = "hh"
    avito = "avito"
    superjob = "superjob"
    rabota = "rabota"
    trudvsem = "trudvsem"
    direct = "direct"


class VacancyFormat(enum.StrEnum):
    online = "online"
    offline = "offline"
    hybrid = "hybrid"


class Vacancy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_vacancy_source_extid"),
        Index("ix_vacancy_city", "city"),
        Index("ix_vacancy_format", "format"),
        Index("ix_vacancy_min_age", "min_age"),
        Index("ix_vacancy_is_spam", "is_spam"),
        Index("ix_vacancy_is_hidden", "is_hidden"),
    )

    source: Mapped[VacancySource] = mapped_column(
        Enum(VacancySource, name="vacancy_source"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    salary_unit: Mapped[str | None] = mapped_column(String(32), default="/мес")
    city: Mapped[str | None] = mapped_column(String(120))
    format: Mapped[VacancyFormat] = mapped_column(
        Enum(VacancyFormat, name="vacancy_format"), default=VacancyFormat.offline
    )
    category: Mapped[str | None] = mapped_column(String(120))
    min_age: Mapped[int] = mapped_column(Integer, default=14)

    url: Mapped[str] = mapped_column(Text, nullable=False)

    # Модерация
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    spam_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    spam_reason: Mapped[str | None] = mapped_column(Text)

    # Скрытие модерацией: если is_hidden=True - не показываем в ленте.
    # Ставится автоматически при N жалобах или вручную админом через WebApp.
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hidden_reason: Mapped[str | None] = mapped_column(Text)

    # Для интеграции с прямыми/featured размещениями
    is_direct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # True, если итоговая аудитория/категория перезаписаны LLM-классификатором
    # (см. services.llm_classify). Используется для аналитики качества.
    llm_classified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    posted_at: Mapped[str | None] = mapped_column(String(64))
