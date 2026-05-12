"""Админ API: жалобы, статистика, действия модерации.

Доступ — только для пользователей с telegram_id ∈ ADMIN_TG_IDS (из .env).
Авторизация через X-Telegram-Init-Data, как и весь остальной API.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import User, Vacancy, VacancyReport, VacancySource
from ..services.moderation_actions import ban_vacancy, restore_vacancy
from .deps import current_telegram_user, get_session

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Auth dependency ─────────────────────────────────────────────────


async def require_admin(tg: dict | None = Depends(current_telegram_user)) -> int:
    """Пускает только пользователей из ADMIN_TG_IDS. Возвращает их telegram_id."""
    if not tg or not tg.get("user"):
        raise HTTPException(401, "Telegram auth required")
    tid = int(tg["user"].get("id") or 0)
    if not tid or tid not in settings.admin_tg_ids:
        raise HTTPException(403, "Admin only")
    return tid


# ── Schemas ─────────────────────────────────────────────────────────


class ReportItem(BaseModel):
    vacancy_id: uuid.UUID
    reports_count: int
    last_report_at: datetime
    title: str
    company: str | None
    city: str | None
    source: str
    url: str
    is_hidden: bool


class HiddenItem(BaseModel):
    vacancy_id: uuid.UUID
    title: str
    company: str | None
    source: str
    url: str
    hidden_reason: str | None
    reports_count: int


class StatsBlock(BaseModel):
    users_total: int
    users_dau: int
    users_onboarded: int
    vacancies_total: int
    vacancies_active: int
    vacancies_hidden: int
    vacancies_spam: int
    by_source: dict[str, int]
    reports_pending: int
    autohides_today: int


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("/me")
async def admin_me(tid: int = Depends(require_admin)) -> dict:
    """Простой ping — для фронта, чтобы понять «я вошёл как админ»."""
    return {"is_admin": True, "telegram_id": tid}


@router.get("/reports", response_model=list[ReportItem])
async def list_reports(
    only_active: bool = True,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    _: int = Depends(require_admin),
) -> list[ReportItem]:
    """Список вакансий, на которые есть жалобы.

    only_active=True — только не скрытые ещё (требуют решения).
    """
    stmt = (
        select(
            VacancyReport.vacancy_id.label("vid"),
            func.count(VacancyReport.id).label("cnt"),
            func.max(VacancyReport.created_at).label("last_at"),
        )
        .group_by(VacancyReport.vacancy_id)
        .order_by(desc("last_at"))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    out: list[ReportItem] = []
    for row in rows:
        v = await session.get(Vacancy, row.vid)
        if v is None:
            continue
        if only_active and v.is_hidden:
            continue
        out.append(
            ReportItem(
                vacancy_id=v.id,
                reports_count=int(row.cnt),
                last_report_at=row.last_at,
                title=v.title,
                company=v.company,
                city=v.city,
                source=v.source.value,
                url=v.url,
                is_hidden=v.is_hidden,
            )
        )
    return out


@router.get("/hidden", response_model=list[HiddenItem])
async def list_hidden(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    _: int = Depends(require_admin),
) -> list[HiddenItem]:
    stmt = (
        select(Vacancy)
        .where(Vacancy.is_hidden.is_(True))
        .order_by(Vacancy.updated_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    out: list[HiddenItem] = []
    for v in rows:
        cnt_res = await session.execute(
            select(func.count(VacancyReport.id)).where(VacancyReport.vacancy_id == v.id)
        )
        out.append(
            HiddenItem(
                vacancy_id=v.id,
                title=v.title,
                company=v.company,
                source=v.source.value,
                url=v.url,
                hidden_reason=v.hidden_reason,
                reports_count=int(cnt_res.scalar_one() or 0),
            )
        )
    return out


@router.post("/vacancies/{vacancy_id}/restore")
async def restore(
    vacancy_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: int = Depends(require_admin),
) -> dict:
    ok = await restore_vacancy(session, vacancy_id)
    if not ok:
        raise HTTPException(404, "Vacancy not found")
    return {"ok": True}


@router.post("/vacancies/{vacancy_id}/ban")
async def ban(
    vacancy_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: int = Depends(require_admin),
) -> dict:
    ok = await ban_vacancy(session, vacancy_id)
    if not ok:
        raise HTTPException(404, "Vacancy not found")
    return {"ok": True}


@router.get("/stats", response_model=StatsBlock)
async def stats(
    session: AsyncSession = Depends(get_session),
    _: int = Depends(require_admin),
) -> StatsBlock:
    now = datetime.now(UTC)
    day_ago = now - timedelta(days=1)

    users_total = (
        await session.execute(select(func.count(User.id)))
    ).scalar_one()
    users_onboarded = (
        await session.execute(select(func.count(User.id)).where(User.onboarded.is_(True)))
    ).scalar_one()
    users_dau = (
        await session.execute(
            select(func.count(User.id)).where(User.updated_at >= day_ago)
        )
    ).scalar_one()

    vac_total = (
        await session.execute(select(func.count(Vacancy.id)))
    ).scalar_one()
    vac_hidden = (
        await session.execute(
            select(func.count(Vacancy.id)).where(Vacancy.is_hidden.is_(True))
        )
    ).scalar_one()
    vac_spam = (
        await session.execute(
            select(func.count(Vacancy.id)).where(Vacancy.is_spam.is_(True))
        )
    ).scalar_one()
    vac_active = (
        await session.execute(
            select(func.count(Vacancy.id)).where(
                Vacancy.is_hidden.is_(False),
                Vacancy.is_spam.is_(False),
            )
        )
    ).scalar_one()

    by_source: dict[str, int] = {}
    for src in VacancySource:
        n = (
            await session.execute(
                select(func.count(Vacancy.id)).where(Vacancy.source == src)
            )
        ).scalar_one()
        by_source[src.value] = int(n)

    reports_pending = (
        await session.execute(
            select(func.count(func.distinct(VacancyReport.vacancy_id)))
            .join(Vacancy, Vacancy.id == VacancyReport.vacancy_id)
            .where(Vacancy.is_hidden.is_(False))
        )
    ).scalar_one()

    autohides_today = (
        await session.execute(
            select(func.count(Vacancy.id)).where(
                Vacancy.is_hidden.is_(True),
                Vacancy.updated_at >= day_ago,
            )
        )
    ).scalar_one()

    return StatsBlock(
        users_total=int(users_total),
        users_dau=int(users_dau),
        users_onboarded=int(users_onboarded),
        vacancies_total=int(vac_total),
        vacancies_active=int(vac_active),
        vacancies_hidden=int(vac_hidden),
        vacancies_spam=int(vac_spam),
        by_source=by_source,
        reports_pending=int(reports_pending),
        autohides_today=int(autohides_today),
    )
