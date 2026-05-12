from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr


class EmployerIn(BaseModel):
    name: str
    contact_email: EmailStr
    contact_phone: str | None = None


class DirectVacancyIn(BaseModel):
    employer: EmployerIn
    title: str
    company: str | None = None
    description: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    salary_unit: str | None = "/час"
    city: str | None = None
    format: Literal["online", "offline", "hybrid"] = "offline"
    category: str | None = None
    min_age: int = 14
    contact: str | None = None
    plan: Literal["basic", "featured", "pinned", "verified"] = "basic"


class PaymentIn(BaseModel):
    direct_vacancy_id: uuid.UUID
    plan: Literal["basic", "featured", "pinned", "verified"]
    return_url: str | None = None


class PaymentOut(BaseModel):
    payment_id: str
    confirmation_url: str
    amount_rub: int
    plan: str
