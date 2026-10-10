"""The candidate's resumes: the survey specialization plus up to two more (services/resumes.py)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant
from app.api.errors import ApiError
from app.core.database import get_db
from app.models import CandidateResume, Participant
from app.services import resumes
from app.services.profile import rebuild_profile
from app.services.search.cache import bump_bank_epoch

router = APIRouter(prefix="/candidates/me/resumes", tags=["candidates"])


class ResumeIn(BaseModel):
    specialization: str = Field(max_length=30)
    grade: str = Field(max_length=20)
    stack: list[str] = Field(default_factory=list, max_length=30)
    summary: str | None = Field(None, max_length=2000)


async def _me(db: AsyncSession, current: dict) -> Participant:
    p = await db.get(Participant, uuid.UUID(current["sub"]), with_for_update=True)
    if p is None:
        raise ApiError(404, "not_found", "Профиль не найден")
    return p


async def _listing(db: AsyncSession, p: Participant) -> dict:
    rows = await resumes.extras(db, p.id)
    primary = resumes.primary_out(p, p.assessed_grade)
    return {"primary": primary, "extras": [resumes.out(r) for r in rows], "extra_max": resumes.EXTRA_MAX}


def _draft(body: ResumeIn, p: Participant) -> resumes.ResumeDraft:
    try:
        return resumes.clean(body.specialization, body.grade, body.stack, body.summary, p.specialization)
    except ValueError as e:
        raise ApiError(422, "validation_error", str(e)) from e


async def _saved(db: AsyncSession, p: Participant) -> dict:
    await rebuild_profile(db, p)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ApiError(409, "conflict", "Резюме по этой специализации уже есть") from e
    await bump_bank_epoch()
    return await _listing(db, p)


@router.get("")
async def list_resumes(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    return await _listing(db, await _me(db, current))


@router.post("", status_code=201)
async def add_resume(body: ResumeIn, current: dict = Depends(get_current_participant),
                     db: AsyncSession = Depends(get_db)):
    p = await _me(db, current)
    if not p.specialization:
        raise ApiError(409, "conflict", "Сначала пройдите опрос: он задаёт основное резюме")
    draft = _draft(body, p)
    rows = await resumes.extras(db, p.id)
    if any(r.specialization == draft.specialization for r in rows):
        raise ApiError(409, "conflict", "Резюме по этой специализации уже есть")
    if len(rows) >= resumes.EXTRA_MAX:
        raise ApiError(409, "conflict", f"Резюме не больше {resumes.EXTRA_MAX + 1}, вместе с основным")
    db.add(CandidateResume(participant_id=p.id, specialization=draft.specialization, grade=draft.grade,
                           stack=draft.stack, summary=draft.summary))
    await db.flush()
    return await _saved(db, p)


@router.put("/{resume_id}")
async def update_resume(resume_id: uuid.UUID, body: ResumeIn, current: dict = Depends(get_current_participant),
                        db: AsyncSession = Depends(get_db)):
    p = await _me(db, current)
    row = await db.get(CandidateResume, resume_id)
    if row is None or row.participant_id != p.id:
        raise ApiError(404, "not_found", "Резюме не найдено")
    draft = _draft(body, p)
    row.specialization, row.grade = draft.specialization, draft.grade
    row.stack, row.summary = draft.stack, draft.summary
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return await _saved(db, p)


@router.delete("/{resume_id}")
async def delete_resume(resume_id: uuid.UUID, current: dict = Depends(get_current_participant),
                        db: AsyncSession = Depends(get_db)):
    p = await _me(db, current)
    row = await db.get(CandidateResume, resume_id)
    if row is None or row.participant_id != p.id:
        raise ApiError(404, "not_found", "Резюме не найдено")
    await db.delete(row)
    await db.flush()
    return await _saved(db, p)
