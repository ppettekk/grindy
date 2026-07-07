from __future__ import annotations

import base64
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import User, Vacancy, VacancyFormat, VacancyReport
from ..schemas import VacancyList, VacancyOut, VacancyReportIn
from ..services.cities import aliases_for
from ..services.ingest import is_suspect
from ..services.moderation_actions import maybe_autohide
from .deps import current_telegram_user, get_session

router = APIRouter(prefix="/api/vacancies", tags=["vacancies"])


def _encode_cursor(created_at_iso: str, vid: uuid.UUID) -> str:
    raw = f"{created_at_iso}|{vid}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    pad = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + pad).decode()
    iso, vid = raw.split("|", 1)
    return iso, uuid.UUID(vid)


def _to_out(v: Vacancy) -> VacancyOut:
    return VacancyOut(
        id=v.id,
        source=v.source.value,
        title=v.title,
        company=v.company,
        description=v.description,
        salary_from=v.salary_from,
        salary_to=v.salary_to,
        salary_unit=v.salary_unit,
        city=v.city,
        format=v.format.value,
        category=v.category,
        min_age=v.min_age,
        url=v.url,
        is_direct=v.is_direct,
        is_verified=v.is_verified,
        is_featured=v.is_featured,
        is_suspect=is_suspect(v.spam_confidence),
        spam_reason=v.spam_reason if is_suspect(v.spam_confidence) else None,
        posted_at=v.posted_at,
        created_at=v.created_at,
    )


@router.get("", response_model=VacancyList)
async def list_vacancies(
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    age: int | None = Query(default=None, description="14, 16, 18 — фильтр по min_age"),
    format: str | None = Query(default=None, regex="^(online|offline|hybrid)$"),
    salary_from: int | None = Query(default=None, ge=0),
    categories: list[str] = Query(default=[]),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> VacancyList:
    # Базовая выборка: не спам, не скрыто.
    stmt = select(Vacancy).where(
        Vacancy.is_spam.is_(False),
        Vacancy.is_hidden.is_(False),
    )

    is_pg = "postgres" in settings.database_url

    # Полнотекстовый поиск
    if q:
        q = q.strip()
    if q:
        if is_pg:
            # plainto_tsquery умеет в стемминг русского; bind через text() с :q
            stmt = stmt.where(
                text("search_vector @@ plainto_tsquery('russian', :q)")
            ).params(q=q)
        else:
            # SQLite: ILIKE по title + company + description
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Vacancy.title.ilike(like),
                    Vacancy.company.ilike(like),
                    Vacancy.description.ilike(like),
                )
            )
    if city:
        # Юзер явно выбрал город — показываем только вакансии этого города
        # или онлайн-вакансии. Вакансии без указанного города НЕ пускаем —
        # иначе пермяк показывается москвичу.
        city_aliases = aliases_for(city)
        if city_aliases:
            stmt = stmt.where(
                or_(
                    *(Vacancy.city.ilike(f"%{a}%") for a in city_aliases),
                    Vacancy.format == VacancyFormat.online,
                )
            )
    if age == 14:
        # 14-летние видят только явные teen-вакансии (min_age<=14).
        stmt = stmt.where(Vacancy.min_age <= 14)
    # age 16/18 — показываем всё (включая 18+). 16-летние фактически
    # увидят и student-вакансии с пометкой «18+» на фронте; это компромисс,
    # потому что строгая teen-выборка слишком пуста, а 18+ часто фактически
    # доступны старшеклассникам (стажировки, ИП родителей, и т.п.).
    if format:
        stmt = stmt.where(Vacancy.format == VacancyFormat(format))
    if salary_from is not None and salary_from > 0:
        stmt = stmt.where(
            or_(
                Vacancy.salary_from >= salary_from,
                Vacancy.salary_to >= salary_from,
            )
        )
    if categories:
        stmt = stmt.where(Vacancy.category.in_(categories))

    if cursor:
        try:
            iso, vid = _decode_cursor(cursor)
        except Exception as e:
            raise HTTPException(400, "Invalid cursor") from e
        stmt = stmt.where(
            or_(
                Vacancy.created_at < iso,  # type: ignore[arg-type]
                and_(Vacancy.created_at == iso, Vacancy.id < vid),  # type: ignore[arg-type]
            )
        )

    stmt = stmt.order_by(
        Vacancy.is_featured.desc(),
        Vacancy.created_at.desc(),
        Vacancy.id.desc(),
    ).limit(limit + 1)

    rows = (await session.execute(stmt)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.created_at.isoformat(), last.id)
        rows = rows[:limit]

    total_stmt = select(func.count(Vacancy.id)).where(
        Vacancy.is_spam.is_(False),
        Vacancy.is_hidden.is_(False),
    )
    total = (await session.execute(total_stmt)).scalar_one()

    return VacancyList(
        items=[_to_out(r) for r in rows],
        next_cursor=next_cursor,
        total=int(total),
    )


@router.get("/{vacancy_id}", response_model=VacancyOut)
async def get_vacancy(
    vacancy_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> VacancyOut:
    v = await session.get(Vacancy, vacancy_id)
    if not v or v.is_spam or v.is_hidden:
        raise HTTPException(404, "Vacancy not found")
    return _to_out(v)


@router.post("/{vacancy_id}/report", status_code=202)
async def report_vacancy(
    vacancy_id: uuid.UUID,
    payload: VacancyReportIn,
    session: AsyncSession = Depends(get_session),
    tg: dict | None = Depends(current_telegram_user),
) -> dict:
    v = await session.get(Vacancy, vacancy_id)
    if not v:
        raise HTTPException(404, "Vacancy not found")

    # Привязываем жалобу к юзеру (по telegram_id из initData), если есть.
    user_pk: uuid.UUID | None = None
    tg_user = (tg or {}).get("user") if tg else None
    if tg_user and tg_user.get("id"):
        u_res = await session.execute(
            select(User).where(User.telegram_id == int(tg_user["id"]))
        )
        u = u_res.scalar_one_or_none()
        if u is not None:
            user_pk = u.id

    session.add(VacancyReport(vacancy_id=v.id, user_id=user_pk, reason=payload.reason))
    await session.commit()

    # Авто-скрытие при достижении порога + уведомление админам.
    await maybe_autohide(session, v.id)

    return {"ok": True}
