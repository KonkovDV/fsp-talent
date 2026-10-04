"""
Assessment service: IRT-based grade evaluation (1PL Rasch, MAP estimation).

P(correct | theta, b) = sigmoid(theta - b)
Prior: theta ~ N(0, 1)
MAP via Newton-Raphson (converges < 10 iter for N=15)

Grade thresholds:
  theta < -0.5  -> junior
  [-0.5, 0.5)   -> middle
  [0.5, 1.5)    -> senior
  >= 1.5        -> lead
"""
from __future__ import annotations

import math
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    GRADE_COOLDOWN_DAYS,
    SESSION_QUESTION_COUNT,
    SESSION_TTL_MINUTES,
    TestAnswer,
    TestQuestion,
    TestSession,
)
from app.models.participant import Participant

GRADE_ORDER = ("junior", "middle", "senior", "lead")
_THRESHOLDS = {"junior": -0.5, "middle": 0.5, "senior": 1.5}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _irt_map(responses: list[tuple[float, bool]], prior_mean: float = 0.0, prior_var: float = 1.0) -> float:
    """MAP estimate of theta via Newton-Raphson."""
    if not responses:
        return 0.0
    theta = prior_mean
    for _ in range(20):
        grad = -(theta - prior_mean) / prior_var
        hess = -1.0 / prior_var
        for b, correct in responses:
            p = _sigmoid(theta - b)
            grad += (1.0 if correct else 0.0) - p
            hess -= p * (1.0 - p)
        if abs(hess) < 1e-12:
            break
        step = grad / hess
        theta -= step
        if abs(step) < 1e-6:
            break
    return max(-4.0, min(4.0, theta))


def _theta_to_grade(theta: float, target_grade: str) -> str:
    if theta < _THRESHOLDS["junior"]:
        result = "junior"
    elif theta < _THRESHOLDS["middle"]:
        result = "middle"
    elif theta < _THRESHOLDS["senior"]:
        result = "senior"
    else:
        result = "lead"
    target_idx = GRADE_ORDER.index(target_grade)
    result_idx = GRADE_ORDER.index(result)
    return GRADE_ORDER[min(result_idx, target_idx)]


async def check_cooldown(db: AsyncSession, participant_id: uuid.UUID) -> datetime | None:
    row = await db.get(Participant, participant_id)
    if row is None:
        return None
    locked_until = getattr(row, "grade_locked_until", None)
    if locked_until and locked_until > datetime.now(UTC):
        return locked_until
    return None


async def get_active_session(db: AsyncSession, participant_id: uuid.UUID) -> TestSession | None:
    result = await db.execute(
        select(TestSession).where(
            and_(
                TestSession.participant_id == participant_id,
                TestSession.status == "in_progress",
                TestSession.expires_at > datetime.now(UTC),
            )
        )
    )
    return result.scalar_one_or_none()


async def expire_stale_sessions(db: AsyncSession, participant_id: uuid.UUID) -> None:
    await db.execute(
        update(TestSession)
        .where(
            and_(
                TestSession.participant_id == participant_id,
                TestSession.status == "in_progress",
                TestSession.expires_at <= datetime.now(UTC),
            )
        )
        .values(status="expired")
    )


async def start_session(
    db: AsyncSession,
    participant_id: uuid.UUID,
    target_grade: str,
    discipline: str | None = None,
) -> tuple[TestSession, list[TestQuestion]]:
    if target_grade not in GRADE_ORDER:
        raise ValueError(f"Invalid grade: {target_grade}")

    await expire_stale_sessions(db, participant_id)

    grades_to_include = [target_grade]
    tgt_idx = GRADE_ORDER.index(target_grade)
    if tgt_idx > 0:
        grades_to_include.append(GRADE_ORDER[tgt_idx - 1])
    if tgt_idx < len(GRADE_ORDER) - 1:
        grades_to_include.append(GRADE_ORDER[tgt_idx + 1])

    q_filter = [
        TestQuestion.active.is_(True),
        TestQuestion.target_grade.in_(grades_to_include),
    ]
    if discipline:
        q_filter.append(TestQuestion.discipline == discipline)

    pool_result = await db.execute(
        select(TestQuestion)
        .where(and_(*q_filter))
        .order_by(TestQuestion.usage_count.asc(), func.random())
        .limit(SESSION_QUESTION_COUNT * 4)
    )
    pool: list[TestQuestion] = list(pool_result.scalars().all())

    if len(pool) < 3:
        fallback = await db.execute(
            select(TestQuestion)
            .where(TestQuestion.active.is_(True), TestQuestion.target_grade.in_(grades_to_include))
            .order_by(TestQuestion.usage_count.asc(), func.random())
            .limit(SESSION_QUESTION_COUNT * 4)
        )
        pool = list(fallback.scalars().all())

    chosen = random.sample(pool, min(SESSION_QUESTION_COUNT, len(pool)))
    question_ids = [str(q.id) for q in chosen]

    session = TestSession(
        participant_id=participant_id,
        target_grade=target_grade,
        discipline=discipline,
        questions_json=question_ids,
        expires_at=datetime.now(UTC) + timedelta(minutes=SESSION_TTL_MINUTES),
    )
    db.add(session)

    if chosen:
        await db.execute(
            update(TestQuestion)
            .where(TestQuestion.id.in_([q.id for q in chosen]))
            .values(usage_count=TestQuestion.usage_count + 1)
        )

    await db.flush()
    return session, chosen


async def submit_answers(
    db: AsyncSession,
    session_id: uuid.UUID,
    participant_id: uuid.UUID,
    answers: list[dict],
) -> TestSession:
    session = await db.get(TestSession, session_id)
    if session is None:
        raise ValueError("Session not found")
    if session.participant_id != participant_id:
        raise ValueError("Forbidden")
    if session.status != "in_progress":
        raise ValueError(f"Session already {session.status}")
    if session.expires_at < datetime.now(UTC):
        session.status = "expired"
        await db.flush()
        raise ValueError("Session expired")

    q_ids = [uuid.UUID(qid) for qid in session.questions_json]
    q_result = await db.execute(select(TestQuestion).where(TestQuestion.id.in_(q_ids)))
    questions: dict[str, TestQuestion] = {str(q.id): q for q in q_result.scalars().all()}

    irt_inputs: list[tuple[float, bool]] = []
    for ans in answers:
        qid = ans.get("question_id")
        ans_text = ans.get("answer", "")
        q = questions.get(str(qid))
        if q is None:
            continue
        is_correct: bool | None = None
        if q.question_type == "mcq" and q.correct_option:
            is_correct = str(ans_text).strip().lower() == str(q.correct_option).strip().lower()
            irt_inputs.append((q.difficulty, is_correct))
        db.add(
            TestAnswer(
                session_id=session_id,
                question_id=q.id,
                answer_text=str(ans_text)[:2000],
                is_correct=is_correct,
            )
        )

    theta = _irt_map(irt_inputs) if irt_inputs else 0.0
    raw_score = sum(1 for _, c in irt_inputs if c) / len(irt_inputs) if irt_inputs else 0.0
    grade_assigned = _theta_to_grade(theta, session.target_grade)

    session.status = "completed"
    session.completed_at = datetime.now(UTC)
    session.irt_theta = theta
    session.score = raw_score
    session.grade_assigned = grade_assigned

    participant = await db.get(Participant, participant_id)
    if participant is not None and participant.grade_locked_until is None:
        participant.grade_locked_until = datetime.now(UTC) + timedelta(days=GRADE_COOLDOWN_DAYS)

    await db.flush()
    return session


async def get_session_with_questions(
    db: AsyncSession,
    session_id: uuid.UUID,
    participant_id: uuid.UUID,
) -> tuple[TestSession, list]:
    session = await db.get(TestSession, session_id)
    if session is None or session.participant_id != participant_id:
        raise ValueError("Not found")
    q_ids = [uuid.UUID(qid) for qid in session.questions_json]
    result = await db.execute(
        select(
            TestQuestion.id,
            TestQuestion.question_text,
            TestQuestion.question_type,
            TestQuestion.options,
            TestQuestion.discipline,
            TestQuestion.target_grade,
        ).where(TestQuestion.id.in_(q_ids))
    )
    q_map = {str(row.id): row for row in result.mappings().all()}
    ordered = [q_map[qid] for qid in [str(i) for i in q_ids] if qid in q_map]
    return session, ordered
