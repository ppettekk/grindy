from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DirectVacancy, Employer, EmployerPlan, VacancyFormat
from ..schemas import DirectVacancyIn, PaymentIn, PaymentOut
from .deps import get_session

router = APIRouter(prefix="/api/employers", tags=["employers"])


PLAN_PRICE_RUB = {
    EmployerPlan.basic: 500,
    EmployerPlan.featured: 1500,
    EmployerPlan.pinned: 1500,
    EmployerPlan.verified: 3000,
}


@router.post("/vacancy", status_code=201)
async def create_direct_vacancy(
    payload: DirectVacancyIn, session: AsyncSession = Depends(get_session)
) -> dict:
    res = await session.execute(
        select(Employer).where(Employer.contact_email == payload.employer.contact_email)
    )
    employer: Employer | None = res.scalar_one_or_none()
    if employer is None:
        employer = Employer(
            name=payload.employer.name,
            contact_email=payload.employer.contact_email,
            contact_phone=payload.employer.contact_phone,
            plan=EmployerPlan(payload.plan),
        )
        session.add(employer)
        await session.flush()

    direct = DirectVacancy(
        employer_id=employer.id,
        title=payload.title,
        company=payload.company or employer.name,
        description=payload.description,
        salary_from=payload.salary_from,
        salary_to=payload.salary_to,
        salary_unit=payload.salary_unit,
        city=payload.city,
        format=VacancyFormat(payload.format),
        category=payload.category,
        min_age=payload.min_age,
        contact=payload.contact,
        is_published=False,  # публикуем после оплаты
        is_featured=payload.plan in {"featured", "pinned"},
    )
    session.add(direct)
    await session.commit()
    await session.refresh(direct)

    return {
        "direct_vacancy_id": str(direct.id),
        "employer_id": str(employer.id),
        "amount_rub": PLAN_PRICE_RUB[EmployerPlan(payload.plan)],
        "plan": payload.plan,
    }


@router.post("/payment", response_model=PaymentOut)
async def create_payment(
    payload: PaymentIn, session: AsyncSession = Depends(get_session)
) -> PaymentOut:
    """Заглушка под ЮКассу. В реале — yookassa Python SDK + webhook."""
    direct = await session.get(DirectVacancy, payload.direct_vacancy_id)
    if direct is None:
        raise HTTPException(404, "Direct vacancy not found")

    plan = EmployerPlan(payload.plan)
    amount = PLAN_PRICE_RUB[plan]

    fake_payment_id = f"stub-{uuid.uuid4().hex[:12]}"
    confirmation_url = (
        f"https://yookassa.example.com/checkout/{fake_payment_id}"
        if not payload.return_url
        else payload.return_url
    )

    # Сразу помечаем как опубликованную в MVP (в реале — после webhook).
    direct.is_published = True
    await session.commit()

    return PaymentOut(
        payment_id=fake_payment_id,
        confirmation_url=confirmation_url,
        amount_rub=amount,
        plan=payload.plan,
    )
