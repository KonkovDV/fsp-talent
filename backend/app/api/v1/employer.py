"""
Employer profile management.

GET  /employer/me   - get profile
PATCH /employer/me  - update company_name, website, description, industry
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.core.database import get_db
from app.models.employer import Employer
from app.services.ats_sandbox import receipt
from app.services.hiring_practice import clean_answers
from app.services.inn import inn_is_valid, published_inn
from app.services.reputation import for_employer
from app.services.trust_level import LABELS, trust_level

router = APIRouter(prefix="/employer", tags=["employer"])


class EmployerProfileOut(BaseModel):
    id: str
    company_name: str
    email: str
    inn: str | None
    website: str | None
    description: str | None
    industry: str | None
    subscription_tier: str
    inn_checked: bool
    trust_level: int
    trust_label: str


class EmployerProfileUpdate(BaseModel):
    company_name: str | None = Field(None, min_length=1, max_length=200)
    website: str | None = Field(None, max_length=200)
    inn: str | None = Field(None, max_length=12)
    description: str | None = Field(None, max_length=4000)
    industry: str | None = Field(None, max_length=200)


@router.get("/me", response_model=EmployerProfileOut)
async def get_me(
    current: dict = Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
):
    emp = await db.get(Employer, uuid.UUID(current["sub"]))
    if emp is None:
        raise HTTPException(404, "Работодатель не найден")
    return EmployerProfileOut(
        id=str(emp.id), company_name=emp.company_name, email=emp.email,
        inn=emp.inn, website=emp.website,
        description=getattr(emp, "description", None),
        industry=getattr(emp, "industry", None),
        subscription_tier=emp.subscription_tier,
        inn_checked=published_inn(emp.inn),
        trust_level=trust_level(emp), trust_label=LABELS[trust_level(emp)],
    )


class HiringPracticeIn(BaseModel):
    feedback: bool = False
    platform_interview: bool = False
    task_review: bool = False
    salary_written: bool = False


@router.get("/me/staff")
async def staff_status(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Only whether to draw the staff links. Nothing from the staff desks is returned here."""
    from app.api.v1.moderation import is_staff
    employer = await db.get(Employer, uuid.UUID(current["sub"]))
    return {"is_staff": is_staff(employer)}


@router.post("/me/hiring-practice")
async def save_hiring_practice(body: HiringPracticeIn, current: dict = Depends(get_current_employer),
                               db: AsyncSession = Depends(get_db)):
    """Store the answers. The response has no level and no count."""
    emp = await db.get(Employer, uuid.UUID(current["sub"]))
    if emp is None:
        raise HTTPException(404, "Работодатель не найден")
    emp.hiring_practice = clean_answers(body.model_dump())
    await db.commit()
    return {"saved": True}


@router.patch("/me", response_model=EmployerProfileOut)
async def update_me(
    body: EmployerProfileUpdate,
    current: dict = Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
):
    emp = await db.get(Employer, uuid.UUID(current["sub"]))
    if emp is None:
        raise HTTPException(404, "Работодатель не найден")
    data = body.model_dump(exclude_unset=True)
    if "inn" in data and data["inn"]:
        digits = "".join(ch for ch in data["inn"] if ch.isdigit())
        if not inn_is_valid(digits):
            raise HTTPException(422, "ИНН не проходит контрольную сумму")
        data["inn"] = digits
    elif "inn" in data:
        data["inn"] = None
    for field, value in data.items():
        if hasattr(emp, field):
            setattr(emp, field, value)
    await db.commit()
    await db.refresh(emp)
    return EmployerProfileOut(
        id=str(emp.id), company_name=emp.company_name, email=emp.email,
        inn=emp.inn, website=emp.website,
        description=getattr(emp, "description", None),
        industry=getattr(emp, "industry", None),
        subscription_tier=emp.subscription_tier,
        inn_checked=published_inn(emp.inn),
        trust_level=trust_level(emp), trust_label=LABELS[trust_level(emp)],
    )


@router.get("/reputation")
async def my_reputation(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """The same facts the candidate sees on an invitation. No single score."""
    emp = await db.get(Employer, uuid.UUID(current["sub"]))
    if emp is None:
        raise HTTPException(404, "Работодатель не найден")
    return await for_employer(db, emp)


@router.post("/ats-sandbox")
async def ats_sandbox(current: dict = Depends(get_current_employer)):
    """Sign one sample event on the stand. No address is called."""
    return receipt(str(current["sub"]))
