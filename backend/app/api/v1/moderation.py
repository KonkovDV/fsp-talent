"""A demo desk for vacancy complaints and model item drafts. It does not exist outside the demo stand.

The printed employer account opens it. Closing a vacancy does not ban a person
and does not hide the candidate bank. A reviewed draft never enters the test.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.core.config import settings
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.models import Complaint, Employer, ItemDraft, Vacancy
from app.services import totp
from app.services.ai import drafts

router = APIRouter(prefix="/moderation", tags=["moderation"])
DRAFTS_PER_MINUTE = 5

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


async def _desk(current: dict, db: AsyncSession, *, factor: bool = True) -> Employer:
    employer = await db.get(Employer, uuid.UUID(current["sub"]))
    if employer is None or not may_moderate(settings.DEMO_MODE, employer.email):
        raise ApiError(404, "not_found", "Раздел не найден")
    if factor and employer.totp_secret and not totp.unlocked(employer.totp_verified_at, datetime.now(UTC)):
        raise ApiError(403, "totp_required")
    return employer


class TotpIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


def _factor_out(employer: Employer) -> dict:
    now = datetime.now(UTC)
    open_now = totp.unlocked(employer.totp_verified_at, now)
    return {"enrolled": bool(employer.totp_secret), "unlocked": open_now,
            "unlocked_until": (employer.totp_verified_at + totp.UNLOCK).isoformat() if open_now else None}


@router.get("/totp")
async def factor_state(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Whether the desk asks for a code. Turning the factor on or off is a server console command."""
    return _factor_out(await _desk(current, db, factor=False))


@router.post("/totp")
async def unlock_desk(body: TotpIn, current: dict = Depends(get_current_employer),
                      db: AsyncSession = Depends(get_db)):
    employer = await _desk(current, db, factor=False)
    if not employer.totp_secret:
        raise ApiError(409, "conflict", "Второй фактор не включён")
    if await too_many(f"moderation:totp:{employer.id}", limit=5, fail_closed=True):
        raise ApiError(429, "rate_limited")
    now = datetime.now(UTC)
    step = totp.accept(totp.open_secret(str(employer.id), employer.totp_secret), body.code, now,
                       employer.totp_last_step)
    if step is None:
        raise ApiError(422, "totp_invalid")
    employer.totp_last_step, employer.totp_verified_at = step, now
    await db.commit()
    return _factor_out(employer)


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


class DraftIn(BaseModel):
    spec: str = Field(max_length=30)
    topic: str = Field(max_length=40)
    level: int = Field(ge=1, le=5)


class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(None, max_length=500)


def _draft_out(row: ItemDraft) -> dict:
    return {
        "id": str(row.id), "spec": row.spec, "topic": row.topic, "level": row.level, "stem": row.stem,
        "key": row.key, "status": row.status, "note": row.note, "created_at": row.created_at.isoformat(),
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


@router.get("/item-drafts")
async def item_drafts(status: Literal["pending", "approved", "rejected"] = "pending",
                      current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Drafts two models agreed on. Approval marks a starting point for a family author; the test never serves it."""
    await _desk(current, db)
    rows = list(await db.scalars(
        select(ItemDraft).where(ItemDraft.status == status).order_by(ItemDraft.created_at.desc()).limit(100)))
    return {"model_ready": drafts.ready() is None, "items": [_draft_out(row) for row in rows]}


@router.post("/item-drafts", status_code=201)
async def request_draft(body: DraftIn, current: dict = Depends(get_current_employer),
                        db: AsyncSession = Depends(get_db)):
    await _desk(current, db)
    wrong = drafts.brief_error(body.spec, body.topic, body.level)
    if wrong:
        raise ApiError(422, "validation_error", wrong)
    if drafts.ready() is not None:
        raise ApiError(503, "unavailable", "Модели для черновиков не подключены: нужны две разные модели")
    if await too_many(f"moderation:drafts:{current['sub']}", limit=DRAFTS_PER_MINUTE):
        raise ApiError(429, "rate_limited")
    verdict, row = await drafts.queue_draft(db, body.spec, body.topic, body.level)
    await db.commit()
    return {"accepted": verdict.accepted, "reason": verdict.reason, "draft": _draft_out(row) if row else None}


@router.post("/item-drafts/{draft_id}/review")
async def review_draft(draft_id: uuid.UUID, body: ReviewIn, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    await _desk(current, db)
    row = await db.get(ItemDraft, draft_id, with_for_update=True)
    if row is None:
        raise ApiError(404, "not_found", "Черновик не найден")
    try:
        drafts.review(row, body.decision, (body.note or "").strip() or None, datetime.now(UTC))
    except ValueError as exc:
        if str(exc) == "identity":
            raise ApiError(422, "validation_error", "В заметке не должно быть имени, почты или телефона") from exc
        raise ApiError(409, "conflict", "Черновик уже разобран") from exc
    await db.commit()
    return _draft_out(row)


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
