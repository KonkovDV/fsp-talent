"""The methodist desk: drafts stay on the moderation routes, quarantine is released here,
and disputed test results are answered here (152-FZ art. 16: an objection to an automated decision).

The flag is not writable through the API. A methodist with a second factor still has to unlock it.
Disputes belong to candidates and sit behind row-level security: the desk reads them in its own short
session with the bypass, opened only after the staff check passed. The desk sees the attempt, not the person.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.api.v1.moderation import _staff
from app.core.database import AsyncSessionLocal, get_db
from app.core.rls import bypass_rls, reset_rls
from app.models import ItemStat, MethodistLog, Participant, Skill
from app.models.assessment import GradeDispute, TestSession, TestSessionItem
from app.services.disputes import DisputeError, clear_failed_checks, decide, desk_row, item_rows
from app.services.notify import Outbox, notify

router = APIRouter(prefix="/methodist", tags=["methodist"])


class ReleaseIn(BaseModel):
    note: str = Field(min_length=3, max_length=500)


@router.get("")
async def me(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    employer = await _staff(current, db)
    return {"methodist": True, "email": employer.email}


@router.get("/quarantine")
async def quarantine(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    await _staff(current, db)
    rows = list(await db.scalars(select(ItemStat).where(ItemStat.status == "quarantined")
                                 .order_by(ItemStat.quarantined_at.desc()).limit(100)))
    return [{
        "item_key": row.item_key, "family_id": row.family_id, "level": row.level,
        "z": round(row.z, 2), "n": row.n,
        "quarantined_at": row.quarantined_at.isoformat() if row.quarantined_at else None,
    } for row in rows]


@router.post("/items/{item_key}/release")
async def release(item_key: str, body: ReleaseIn, current: dict = Depends(get_current_employer),
                  db: AsyncSession = Depends(get_db)):
    from app.services.staff import release_key

    employer = await _staff(current, db)
    row = await db.get(ItemStat, item_key)
    if row is None:
        raise ApiError(404, "not_found", "Задание не найдено")
    try:
        release_key(row, body.note.strip(), datetime.now(UTC))
    except ValueError as exc:
        if str(exc) == "identity":
            raise ApiError(422, "validation_error", "В заметке не должно быть имени, почты или телефона") from exc
        raise ApiError(409, "conflict", "Задание не в карантине") from exc
    db.add(MethodistLog(employer_id=employer.id, action="release", subject=item_key[:80],
                        note=body.note.strip(), created_at=datetime.now(UTC)))
    await db.commit()
    return {"item_key": row.item_key, "status": row.status}


@router.get("/log")
async def log(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    await _staff(current, db)
    rows = list(await db.scalars(select(MethodistLog).order_by(MethodistLog.created_at.desc()).limit(50)))
    return [{"id": str(row.id), "action": row.action, "subject": row.subject, "note": row.note,
             "created_at": row.created_at.isoformat()} for row in rows]


@asynccontextmanager
async def _desk_session():
    """A short session that may read every candidate's dispute. Open it only after `_staff` passed."""
    token = bypass_rls()
    try:
        async with AsyncSessionLocal() as session:
            yield session
    finally:
        reset_rls(token)


class DecisionIn(BaseModel):
    action: Literal["uphold", "void"]
    note: str = Field(min_length=10, max_length=1000, description="Ответ кандидату: что проверено и почему так решено")


@router.get("/disputes")
async def disputes(state: Literal["open", "closed", "all"] = Query("open"),
                   current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Disputed results, the oldest open first, with the legal deadline of 30 days."""
    await _staff(current, db)
    now = datetime.now(UTC)
    async with _desk_session() as desk:
        query = select(GradeDispute)
        if state == "open":
            query = query.where(GradeDispute.status == "open").order_by(GradeDispute.created_at)
        elif state == "closed":
            query = query.where(GradeDispute.status != "open").order_by(GradeDispute.decided_at.desc())
        else:
            query = query.order_by(GradeDispute.created_at.desc())
        rows = list(await desk.scalars(query.limit(100)))
        out = []
        for row in rows:
            session = await desk.get(TestSession, row.session_id)
            out.append(desk_row(row, session, now))
    return out


@router.get("/disputes/{dispute_id}")
async def dispute_detail(dispute_id: uuid.UUID, current: dict = Depends(get_current_employer),
                         db: AsyncSession = Depends(get_db)):
    """One attempt in full: the served items, the given and the right answer, the time spent."""
    await _staff(current, db)
    async with _desk_session() as desk:
        row = await desk.get(GradeDispute, dispute_id)
        if row is None:
            raise ApiError(404, "not_found", "Обращение не найдено")
        session = await desk.get(TestSession, row.session_id)
        items = list(await desk.scalars(
            select(TestSessionItem).where(TestSessionItem.session_id == row.session_id)
            .order_by(TestSessionItem.seq)))
        return {**desk_row(row, session, datetime.now(UTC)), "items": item_rows(items)}


@router.post("/disputes/{dispute_id}/decision")
async def decide_dispute(dispute_id: uuid.UUID, body: DecisionIn, current: dict = Depends(get_current_employer),
                         db: AsyncSession = Depends(get_db)):
    """Answer the candidate. Upholding keeps the result; voiding a failed attempt removes its consequences.

    Nobody sets a grade here. The decision, the methodist and the time are logged; the candidate gets a
    notification and a letter with the answer.
    """
    employer = await _staff(current, db)
    now = datetime.now(UTC)
    outbox = Outbox()
    async with _desk_session() as desk:
        row = await desk.get(GradeDispute, dispute_id, with_for_update=True)
        if row is None:
            raise ApiError(404, "not_found", "Обращение не найдено")
        session = await desk.get(TestSession, row.session_id, with_for_update=True)
        if session is None:
            raise ApiError(404, "not_found", "Попытка не найдена")
        try:
            status = decide(row, session, body.action, body.note, employer.id, now)
        except DisputeError as exc:
            reason = str(exc)
            if reason == "closed":
                raise ApiError(409, "conflict", "Обращение уже рассмотрено") from exc
            if reason == "not_voidable":
                raise ApiError(409, "conflict", "Аннулировать можно только законченный тест на грейд, "
                                                "который грейд не подтвердил") from exc
            if reason == "identity":
                raise ApiError(422, "validation_error", "В ответе не должно быть имени, почты или телефона") from exc
            raise ApiError(422, "validation_error", "Ответ — от 10 до 1000 символов") from exc
        if status == "voided":
            skills = list(await desk.scalars(select(Skill).where(Skill.participant_id == row.participant_id)))
            clear_failed_checks(skills, session.completed_at)
            person = await desk.get(Participant, row.participant_id)
            # Erasure already wiped skills; rebuilding would resurrect rows for a deleted account.
            if person is not None and getattr(person, "deleted_at", None) is None:
                from app.services.profile import rebuild_profile
                await rebuild_profile(desk, person)
        desk.add(MethodistLog(employer_id=employer.id, action=f"dispute_{status}", subject=f"dispute:{row.id}"[:80],
                              note=row.decision_note[:500], created_at=now))
        title = "Обращение по тесту рассмотрено"
        body_text = ("Методист аннулировал попытку: она не мешает пересдаче и не опускает грейд в подборке. "
                     if status == "voided" else "Методист проверил тест и оставил результат. ")
        await notify(desk, outbox, "participant", row.participant_id, "dispute_decided", title,
                     body_text + f"Ответ: {row.decision_note}", "/candidate/assessment")
        await desk.commit()
        result = desk_row(row, session, now)
    await outbox.deliver()
    return result
