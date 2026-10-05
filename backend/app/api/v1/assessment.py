"""
Assessment API.

POST /assessment/start          - start test session
GET  /assessment/{session_id}   - get session (no answers revealed)
POST /assessment/{session_id}/submit - submit + grade
GET  /assessment/cooldown       - check cooldown status
GET  /assessment/history        - list past sessions (paginated)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.models import Participant
from app.models.assessment import GRADE_ORDER, TestSession
from app.services.assessment import (
    QuestionBankError,
    check_cooldown,
    check_retake_interval,
    get_active_session,
    get_session_with_questions,
    start_session,
    submit_answers,
)
from app.services.profile import rebuild_profile

router = APIRouter(prefix="/assessment", tags=["assessment"])


class StartSessionIn(BaseModel):
    target_grade: str = Field(..., description="junior | middle | senior | lead")
    discipline: str | None = Field(None, max_length=80)


class AnswerIn(BaseModel):
    question_id: str
    answer: str = Field(..., max_length=4000)


class SubmitIn(BaseModel):
    answers: list[AnswerIn] = Field(..., min_length=1, max_length=30)


class QuestionOut(BaseModel):
    id: str
    question_text: str
    question_type: str
    options: list[dict] | None
    discipline: str
    target_grade: str


class SessionOut(BaseModel):
    session_id: str
    status: str
    target_grade: str
    discipline: str | None
    expires_at: str
    questions: list[QuestionOut]


class ResultOut(BaseModel):
    session_id: str
    status: str
    score: float | None
    irt_theta: float | None
    # Grade this result corresponds to (may be below the target; None = too low to confirm anything).
    grade_assigned: str | None
    # Grade confirmed on the profile after this session, and what the session did to it.
    confirmed_grade: str | None
    outcome: str  # first_confirmation | upgrade | confirmed_again | kept_higher_grade | not_passed
    grade_locked_until: str | None
    completed_at: str | None


def _q_out(q) -> QuestionOut:
    if isinstance(q, dict):
        return QuestionOut(
            id=str(q["id"]), question_text=q["question_text"],
            question_type=q["question_type"], options=q["options"],
            discipline=q["discipline"], target_grade=q["target_grade"],
        )
    return QuestionOut(
        id=str(q.id), question_text=q.question_text,
        question_type=q.question_type, options=q.options,
        discipline=q.discipline, target_grade=q.target_grade,
    )


@router.post("/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def start_test(
    body: StartSessionIn,
    current: dict = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    if body.target_grade not in GRADE_ORDER:
        raise HTTPException(400, f"Invalid grade. Allowed: {list(GRADE_ORDER)}")
    participant_id = uuid.UUID(current["sub"])
    if await too_many(f"assessment_start:{participant_id}", limit=3, window_seconds=3600):
        raise HTTPException(429, "Too many attempts, wait an hour")
    locked_until = await check_cooldown(db, participant_id)
    if locked_until:
        raise HTTPException(429, f"Grade change locked until {locked_until.isoformat()}")
    retake_at = await check_retake_interval(db, participant_id, body.target_grade)
    if retake_at:
        raise HTTPException(429, f"This grade can be retaken after {retake_at.isoformat()}")
    existing = await get_active_session(db, participant_id)
    if existing:
        raise HTTPException(409, f"Session {existing.id} already active, expires {existing.expires_at.isoformat()}")
    try:
        session, questions = await start_session(db, participant_id, body.target_grade, body.discipline)
        await db.commit()
    except QuestionBankError as e:
        raise HTTPException(503, str(e)) from e
    except IntegrityError as e:
        # uix_one_active_session: a parallel start request won the race.
        await db.rollback()
        raise HTTPException(409, "A test session is already active") from e
    await db.refresh(session)
    return SessionOut(
        session_id=str(session.id), status=session.status,
        target_grade=session.target_grade, discipline=session.discipline,
        expires_at=session.expires_at.isoformat(),
        questions=[_q_out(q) for q in questions],
    )


@router.get("/cooldown")
async def cooldown_status(
    current: dict = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    participant_id = uuid.UUID(current["sub"])
    locked_until = await check_cooldown(db, participant_id)
    return {"locked": locked_until is not None, "locked_until": locked_until.isoformat() if locked_until else None}


@router.get("/history")
async def session_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current: dict = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    participant_id = uuid.UUID(current["sub"])
    result = await db.execute(
        select(TestSession)
        .where(TestSession.participant_id == participant_id)
        .order_by(desc(TestSession.started_at))
        .limit(limit).offset(offset)
    )
    sessions = result.scalars().all()
    return {
        "items": [{
            "session_id": str(s.id), "status": s.status,
            "target_grade": s.target_grade, "grade_assigned": s.grade_assigned,
            "score": s.score, "irt_theta": s.irt_theta,
            "started_at": s.started_at.isoformat(),
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        } for s in sessions],
        "total": len(sessions), "limit": limit, "offset": offset,
    }


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: uuid.UUID,
    current: dict = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    participant_id = uuid.UUID(current["sub"])
    try:
        session, questions = await get_session_with_questions(db, session_id, participant_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return SessionOut(
        session_id=str(session.id), status=session.status,
        target_grade=session.target_grade, discipline=session.discipline,
        expires_at=session.expires_at.isoformat(),
        questions=[_q_out(q) for q in questions],
    )


@router.post("/{session_id}/submit", response_model=ResultOut)
async def submit(
    session_id: uuid.UUID,
    body: SubmitIn,
    current: dict = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    participant_id = uuid.UUID(current["sub"])
    try:
        session, decision = await submit_answers(
            db, session_id, participant_id,
            [{"question_id": a.question_id, "answer": a.answer} for a in body.answers],
        )
    except ValueError as e:
        detail = str(e)
        code = 404 if "not found" in detail.lower() else 409
        raise HTTPException(code, detail) from e
    participant = await db.get(Participant, participant_id)
    if participant is not None and decision.applied:
        # The confirmed grade feeds the category employers see and filter by.
        await rebuild_profile(db, participant)
    await db.commit()
    await db.refresh(session)
    return ResultOut(
        session_id=str(session.id), status=session.status,
        score=session.score, irt_theta=session.irt_theta,
        grade_assigned=session.grade_assigned,
        confirmed_grade=decision.assessed_grade,
        outcome=decision.reason,
        grade_locked_until=decision.locked_until.isoformat() if decision.locked_until else None,
        completed_at=session.completed_at.isoformat() if session.completed_at else None,
    )
