"""A demo desk for vacancy complaints. It does not exist outside the demo stand.

The printed employer account opens it. Closing a vacancy does not ban a person
and does not hide the candidate bank.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.core.config import settings
from app.core.database import get_db
from app.models import Complaint, Employer, Vacancy

router = APIRouter(prefix="/moderation", tags=["moderation"])

MODERATORS = frozenset({"hr@sibcode.demo"})
LABELS = {
    "не_вакансия": "fake",
    "зарплата_не_та": "salary",
    "оскорбление": "discrimination",
    "сбор_данных": "spam",
    "другое": "other",
}


def may_moderate(demo: bool, email: str | None) -> bool:
    return bool(demo) and (email or "") in MODERATORS


async def _desk(current: dict, db: AsyncSession) -> Employer:
    employer = await db.get(Employer, uuid.UUID(current["sub"]))
    if employer is None or not may_moderate(settings.DEMO_MODE, employer.email):
        raise ApiError(404, "not_found", "Раздел не найден")
    return employer


@router.get("/complaints")
async def complaints(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    await _desk(current, db)
    rows = list(await db.scalars(select(Complaint).order_by(Complaint.created_at.desc()).limit(100)))
    return [{
        "id": str(row.id),
        "reason": LABELS.get(row.reason, "other"),
        "vacancy_id": str(row.vacancy_id) if row.vacancy_id else None,
        "offer_id": str(row.offer_id) if row.offer_id else None,
        "created_at": row.created_at.isoformat(),
    } for row in rows]


@router.post("/vacancies/{vacancy_id}/close")
async def close_vacancy(vacancy_id: uuid.UUID, current: dict = Depends(get_current_employer),
                        db: AsyncSession = Depends(get_db)):
    await _desk(current, db)
    vacancy = await db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise ApiError(404, "not_found", "Вакансия не найдена")
    if not vacancy.is_open:
        raise ApiError(409, "conflict", "Вакансия уже закрыта")
    vacancy.is_open = False
    await db.commit()
    return {"id": str(vacancy.id), "is_open": False}
