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


class EmployerProfileUpdate(BaseModel):
    company_name: str | None = Field(None, min_length=1, max_length=200)
    website: str | None = Field(None, max_length=500)
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
    )


@router.patch("/me", response_model=EmployerProfileOut)
async def update_me(
    body: EmployerProfileUpdate,
    current: dict = Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
):
    emp = await db.get(Employer, uuid.UUID(current["sub"]))
    if emp is None:
        raise HTTPException(404, "Работодатель не найден")
    for field, value in body.model_dump(exclude_none=True).items():
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
    )
