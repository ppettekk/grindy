from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class EmployerPlan(enum.StrEnum):
    basic = "basic"
    featured = "featured"
    pinned = "pinned"
    verified = "verified"


class Employer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "employers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    plan: Mapped[EmployerPlan] = mapped_column(
        Enum(EmployerPlan, name="employer_plan"), default=EmployerPlan.basic
    )
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
