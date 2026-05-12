from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import SavedVacancy, User, Vacancy
from ..schemas import UserIn, UserOut, UserUpdate, VacancyList, VacancyOut
from ..services.ingest import is_suspect
from ..services.subscription import is_subscribed
from ..services.telegram import get_bot
from .deps import get_session

router = APIRouter(prefix="/api/users", tags=["users"])


def _vacancy_to_out(v: Vacancy) -> VacancyOut:
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


async def _get_user_or_404(session: AsyncSession, telegram_id: int) -> User:
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.post("", response_model=UserOut)
async def upsert_user(
    payload: UserIn, session: AsyncSession = Depends(get_session)
) -> UserOut:
    res = await session.execute(
        select(User).where(User.telegram_id == payload.telegram_id)
    )
    user = res.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name,
            city=payload.city,
            age_filter=payload.age_filter,
            format_filter=payload.format_filter,
            categories=payload.categories,
        )
        session.add(user)
    else:
        user.username = payload.username or user.username
        user.first_name = payload.first_name or user.first_name
        user.city = payload.city or user.city
        user.age_filter = payload.age_filter
        user.format_filter = payload.format_filter
        user.categories = payload.categories or user.categories
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.get("/{telegram_id}", response_model=UserOut)
async def get_user(
    telegram_id: int, session: AsyncSession = Depends(get_session)
) -> UserOut:
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")
    return UserOut.model_validate(user)


@router.patch("/{telegram_id}", response_model=UserOut)
async def update_user(
    telegram_id: int,
    payload: UserUpdate,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(user, k, v)

    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


# ===== Подписка на канал =====


@router.get("/{telegram_id}/subscription")
async def check_subscription(telegram_id: int) -> dict:
    """Проверяет, подписан ли пользователь на обязательный канал.

    Возвращает:
        - required: фича включена (REQUIRE_CHANNEL задан и BOT_TOKEN есть)
        - subscribed: подписан ли (если фича выключена — всегда True)
        - channel: handle канала ("@grindywork") или None
    """
    channel = (settings.require_channel or "").strip()
    if not channel:
        return {"required": False, "subscribed": True, "channel": None}

    bot = get_bot()
    if bot is None:
        # BOT_TOKEN не задан — не блокируем, чтобы dev-окружение работало.
        return {"required": False, "subscribed": True, "channel": channel}

    ok = await is_subscribed(bot, telegram_id, channel)
    return {"required": True, "subscribed": ok, "channel": channel}


# ===== Сохранённые вакансии =====


@router.get("/{telegram_id}/saved", response_model=VacancyList)
async def list_saved(
    telegram_id: int, session: AsyncSession = Depends(get_session)
) -> VacancyList:
    user = await _get_user_or_404(session, telegram_id)
    q = (
        select(Vacancy)
        .join(SavedVacancy, SavedVacancy.vacancy_id == Vacancy.id)
        .where(SavedVacancy.user_id == user.id)
        .order_by(SavedVacancy.created_at.desc())
    )
    rows = (await session.execute(q)).scalars().all()
    items = [_vacancy_to_out(v) for v in rows]
    return VacancyList(items=items, next_cursor=None, total=len(items))


@router.post("/{telegram_id}/saved/{vacancy_id}", status_code=201)
async def save_vacancy(
    telegram_id: int,
    vacancy_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await _get_user_or_404(session, telegram_id)
    v = await session.get(Vacancy, vacancy_id)
    if v is None:
        raise HTTPException(404, "Vacancy not found")
    # Идемпотентно: если уже сохранена, ничего не делаем.
    existing = await session.execute(
        select(SavedVacancy).where(
            SavedVacancy.user_id == user.id,
            SavedVacancy.vacancy_id == vacancy_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        session.add(SavedVacancy(user_id=user.id, vacancy_id=vacancy_id))
        await session.commit()
    return {"ok": True}


@router.delete("/{telegram_id}/saved/{vacancy_id}", status_code=200)
async def unsave_vacancy(
    telegram_id: int,
    vacancy_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await _get_user_or_404(session, telegram_id)
    await session.execute(
        delete(SavedVacancy).where(
            SavedVacancy.user_id == user.id,
            SavedVacancy.vacancy_id == vacancy_id,
        )
    )
    await session.commit()
    return {"ok": True}
