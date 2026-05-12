from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceLiteral = Literal["hh", "avito", "superjob", "rabota", "trudvsem", "direct"]
FormatLiteral = Literal["online", "offline", "hybrid"]


class VacancyDTO(BaseModel):
    """DTO от парсеров — то, что они отдают в ingest-сервис."""

    source: SourceLiteral
    external_id: str
    title: str
    company: str | None = None
    description: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    salary_unit: str | None = "/мес"
    city: str | None = None
    format: FormatLiteral = "offline"
    category: str | None = None
    min_age: int = 14
    url: str
    posted_at: str | None = None


class VacancyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: SourceLiteral
    title: str
    company: str | None = None
    description: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    salary_unit: str | None = None
    city: str | None = None
    format: FormatLiteral
    category: str | None = None
    min_age: int
    url: str
    is_direct: bool
    is_verified: bool
    is_featured: bool
    is_suspect: bool = False
    spam_reason: str | None = None
    posted_at: str | None = None
    created_at: datetime


class VacancyList(BaseModel):
    items: list[VacancyOut]
    next_cursor: str | None = None
    total: int


class VacancyFilters(BaseModel):
    q: str | None = None
    city: str | None = None
    age: int | None = Field(default=None, description="14 / 16 / 18")
    format: FormatLiteral | None = None
    salary_from: int | None = None
    categories: list[str] = Field(default_factory=list)
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=50)


class VacancyReportIn(BaseModel):
    reason: str | None = None
