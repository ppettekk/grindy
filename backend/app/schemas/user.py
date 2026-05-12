from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserIn(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    city: str | None = None
    age_filter: int = 16
    format_filter: Literal["all", "online", "offline"] = "all"
    categories: list[str] = Field(default_factory=list)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    city: str | None = None
    age_filter: int
    format_filter: str
    categories: list[str]
    notifications_morning: bool
    notifications_evening: bool
    notifications_realtime: bool = False
    onboarded: bool
    created_at: datetime


class UserUpdate(BaseModel):
    city: str | None = None
    age_filter: int | None = None
    format_filter: Literal["all", "online", "offline"] | None = None
    categories: list[str] | None = None
    notifications_morning: bool | None = None
    notifications_evening: bool | None = None
    notifications_realtime: bool | None = None
    onboarded: bool | None = None
