"""
Assessment service: 2PL IRT grade evaluation (MAP estimate) and the grade-change policy.

P(correct | theta, a, b) = sigmoid(a * (theta - b))
  a = discrimination (TestQuestion.discrimination), b = difficulty (TestQuestion.difficulty)
Prior: theta ~ N(0, 1); MAP by Newton-Raphson.

Grade thresholds (theta):
  below -1.5      -> not confirmed (nothing is assigned)
  [-1.5, -0.5)    -> junior
  [-0.5, 0.5)     -> middle
  [0.5, 1.5)      -> senior
  >= 1.5          -> lead

Policy (TZ section 2, "Категория и грейд"):
  * A test never lowers a confirmed grade. A failed attempt at the target grade changes nothing in
    the profile; the candidate may take a test one level lower instead.
  * A confident result may raise the grade by one level above the target ("кандидат, справившийся
    уверенно, может повысить грейд"). "Confident" means the next level's threshold is below
    theta - UPGRADE_MARGIN_SE * SE(theta). In a simulation with candidates who declare their true
    grade, the point estimate alone falsely upgraded 13% of them; the 1 SE margin cuts that to 1% and
    raises retest agreement on the exact grade from 55% to 70%.
  * Only an actual grade change starts the cooldown (GRADE_COOLDOWN_DAYS). A failed attempt does not,
    otherwise the candidate could not retake a lower level as the TZ requires. Retakes of the same
    target grade are throttled separately (RETAKE_INTERVAL_DAYS).

Anti-gaming rules (see docs/TRIAGE_REDTEAM_MURDERBOARD_2026-10-05.md):
  * Every served question is scored. A skipped question counts as wrong; the previous code ignored
    it, so answering only the items you knew inflated theta, and answering none returned theta = 0,
    which mapped to "middle".
  * A session needs at least MIN_SCORED_QUESTIONS gradable items, otherwise it is not started.
"""
from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    GRADE_COOLDOWN_DAYS,
    GRADE_ORDER,
    SESSION_QUESTION_COUNT,
    SESSION_TTL_MINUTES,
    TestAnswer,
    TestQuestion,
    TestSession,
)
from app.models.participant import Participant

RETAKE_INTERVAL_DAYS = 7
MIN_SCORED_QUESTIONS = 5
UPGRADE_MARGIN_SE = 1.0
_NOT_CONFIRMED_BELOW = -1.5
_THRESHOLDS = {"junior": -0.5, "middle": 0.5, "senior": 1.5}


class QuestionBankError(RuntimeError):
    """The bank cannot supply enough gradable questions for a fair session."""


def _sigmoid(x: float) -> float:
    # Numerically stable logistic function
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _irt_map(
    responses: list[tuple[float, float, bool]],  # (difficulty b, discrimination a, correct)
    prior_mean: float = 0.0,
    prior_var: float = 1.0,
) -> float:
    """MAP estimate of theta by Newton-Raphson under the 2PL model.

    With no responses the estimate is the prior mean. Callers must not grade a session on an empty
    response list (see submit_answers): that would hand out theta = 0 for free.
    The log-posterior is strictly concave (Gaussian prior), so Newton converges from the prior mean.
    """
    if not responses:
        return prior_mean
    theta = prior_mean
    for _ in range(25):
        grad = -(theta - prior_mean) / prior_var
        hess = -1.0 / prior_var
        for b, a, correct in responses:
            p = _sigmoid(a * (theta - b))
            grad += a * ((1.0 if correct else 0.0) - p)
            hess -= a * a * p * (1.0 - p)
        step = grad / hess
        theta -= step
        if abs(step) < 1e-8:
            break
    return max(-4.0, min(4.0, theta))


def posterior_se(theta: float, responses: list[tuple[float, float, bool]], prior_var: float = 1.0) -> float:
    """Standard error of the MAP estimate: 1 / sqrt(prior precision + 2PL test information at theta)."""
    info = 1.0 / prior_var
    for b, a, _ in responses:
        p = _sigmoid(a * (theta - b))
        info += a * a * p * (1.0 - p)
    return 1.0 / math.sqrt(info)


def grade_from_theta(theta: float) -> str | None:
    """Grade a theta corresponds to, or None when the result is too low to confirm anything."""
    if theta < _NOT_CONFIRMED_BELOW:
        return None
    if theta < _THRESHOLDS["junior"]:
        return "junior"
    if theta < _THRESHOLDS["middle"]:
        return "middle"
    if theta < _THRESHOLDS["senior"]:
        return "senior"
    return "lead"


def earned_grade(theta: float, target_grade: str, se: float = 0.0) -> str | None:
    """Grade a session targeting `target_grade` can vouch for, or None.

    A session draws items from target-1 .. target+1, so it measures only that band. Above it the
    result is capped at target+1, and that upgrade needs theta - UPGRADE_MARGIN_SE * se to clear the
    next threshold; below target-1 it says "not confirmed" rather than extrapolating (all answers
    wrong on a senior test must not read as "junior confirmed").
    """
    base = grade_from_theta(theta)
    if base is None:
        return None
    target_idx = GRADE_ORDER.index(target_grade)
    base_idx = GRADE_ORDER.index(base)
    if base_idx < target_idx - 1:
        return None
    if base_idx > target_idx:
        upper = GRADE_ORDER[min(target_idx + 1, len(GRADE_ORDER) - 1)]
        confident = grade_from_theta(theta - UPGRADE_MARGIN_SE * se)
        if confident is not None and GRADE_ORDER.index(confident) >= GRADE_ORDER.index(upper):
            return upper
        return target_grade
    return base


def passed_target(earned: str | None, target_grade: str) -> bool:
    return earned is not None and GRADE_ORDER.index(earned) >= GRADE_ORDER.index(target_grade)


@dataclass(frozen=True)
class GradeDecision:
    """What a completed session does to the profile."""
    assessed_grade: str | None   # confirmed grade after applying the result
    applied: bool                # the profile's confirmed grade changed (first confirmation or upgrade)
    upgraded: bool               # a previously confirmed grade was raised
    locked_until: datetime | None
    reason: str                  # first_confirmation | upgrade | confirmed_again | kept_higher_grade | not_passed


def decide_grade(current: str | None, earned: str | None, target_grade: str, now: datetime) -> GradeDecision:
    """Pure policy function: confirmed grade + session outcome -> new confirmed grade and cooldown."""
    if earned is None or not passed_target(earned, target_grade):
        return GradeDecision(current, False, False, None, "not_passed")
    if current is None:
        # First confirmation is the baseline, not a change: it does not start the cooldown.
        return GradeDecision(earned, True, False, None, "first_confirmation")
    if GRADE_ORDER.index(earned) > GRADE_ORDER.index(current):
        return GradeDecision(earned, True, True, now + timedelta(days=GRADE_COOLDOWN_DAYS), "upgrade")
    if earned == current:
        return GradeDecision(current, False, False, None, "confirmed_again")
    return GradeDecision(current, False, False, None, "kept_higher_grade")


async def check_cooldown(db: AsyncSession, participant_id: uuid.UUID) -> datetime | None:
    row = await db.get(Participant, participant_id)
    if row is None:
        return None
    locked_until = getattr(row, "grade_locked_until", None)
    if locked_until and locked_until > datetime.now(UTC):
        return locked_until
    return None


async def check_retake_interval(
    db: AsyncSession, participant_id: uuid.UUID, target_grade: str,
) -> datetime | None:
    """When the candidate may retake the same target grade, or None if they may start now."""
    since = datetime.now(UTC) - timedelta(days=RETAKE_INTERVAL_DAYS)
    last = await db.scalar(
        select(func.max(TestSession.completed_at)).where(
            TestSession.participant_id == participant_id,
            TestSession.target_grade == target_grade,
            TestSession.status == "completed",
            TestSession.completed_at > since,
        )
    )
    return last + timedelta(days=RETAKE_INTERVAL_DAYS) if last else None


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


def _gradable(q: TestQuestion) -> bool:
    return q.question_type == "mcq" and bool(q.correct_option)


async def start_session(
    db: AsyncSession,
    participant_id: uuid.UUID,
    target_grade: str,
    discipline: str | None = None,
) -> tuple[TestSession, list[TestQuestion]]:
    if target_grade not in GRADE_ORDER:
        raise ValueError(f"Invalid grade: {target_grade}")

    await expire_stale_sessions(db, participant_id)

    tgt_idx = GRADE_ORDER.index(target_grade)
    grades_to_include = [target_grade]
    if tgt_idx > 0:
        grades_to_include.append(GRADE_ORDER[tgt_idx - 1])
    if tgt_idx < len(GRADE_ORDER) - 1:
        grades_to_include.append(GRADE_ORDER[tgt_idx + 1])

    base_filter = [
        TestQuestion.active.is_(True),
        TestQuestion.question_type == "mcq",
        TestQuestion.correct_option.is_not(None),
        TestQuestion.target_grade.in_(grades_to_include),
    ]

    async def _pool(extra: list) -> list[TestQuestion]:
        rows = await db.execute(
            select(TestQuestion)
            .where(and_(*base_filter, *extra))
            .order_by(TestQuestion.usage_count.asc(), func.random())
            .limit(SESSION_QUESTION_COUNT * 4)
        )
        return list(rows.scalars().all())

    pool = await _pool([TestQuestion.discipline == discipline] if discipline else [])
    if len(pool) < MIN_SCORED_QUESTIONS and discipline:
        # The bank is thin for this discipline: fall back to all disciplines at these grades.
        pool = await _pool([])
    if len(pool) < MIN_SCORED_QUESTIONS:
        raise QuestionBankError(
            f"Question bank has {len(pool)} gradable questions for grade {target_grade}; "
            f"at least {MIN_SCORED_QUESTIONS} are required"
        )

    chosen = random.sample(pool, min(SESSION_QUESTION_COUNT, len(pool)))
    session = TestSession(
        participant_id=participant_id,
        target_grade=target_grade,
        discipline=discipline,
        questions_json=[str(q.id) for q in chosen],
        expires_at=datetime.now(UTC) + timedelta(minutes=SESSION_TTL_MINUTES),
    )
    db.add(session)
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
) -> tuple[TestSession, GradeDecision]:
    # Row lock: two concurrent submits of one session must not both be graded.
    session = await db.get(TestSession, session_id, with_for_update=True)
    if session is None or session.participant_id != participant_id:
        raise ValueError("Session not found")
    if session.status != "in_progress":
        raise ValueError(f"Session already {session.status}")
    now = datetime.now(UTC)
    if session.expires_at < now:
        session.status = "expired"
        await db.flush()
        raise ValueError("Session expired")

    q_ids = [uuid.UUID(qid) for qid in session.questions_json]
    q_rows = await db.execute(select(TestQuestion).where(TestQuestion.id.in_(q_ids)))
    questions: dict[str, TestQuestion] = {str(q.id): q for q in q_rows.scalars().all()}

    # First answer per question wins; ids that were not served in this session are ignored.
    given: dict[str, str] = {}
    for ans in answers:
        qid = str(ans.get("question_id"))
        if qid in questions and qid not in given:
            given[qid] = str(ans.get("answer", "")).strip()

    irt_inputs: list[tuple[float, float, bool]] = []
    for qid in session.questions_json:
        q = questions.get(str(qid))
        if q is None or not _gradable(q):
            continue
        text = given.get(str(qid))
        # A skipped question is a wrong answer.
        is_correct = text is not None and text.lower() == str(q.correct_option).strip().lower()
        a = q.discrimination if q.discrimination is not None else 1.0
        irt_inputs.append((q.difficulty, a, is_correct))
        db.add(TestAnswer(session_id=session_id, question_id=q.id,
                          answer_text=text[:2000] if text is not None else None, is_correct=is_correct))

    if len(irt_inputs) < MIN_SCORED_QUESTIONS:
        raise ValueError("Session has too few gradable questions")

    theta = _irt_map(irt_inputs)
    earned = earned_grade(theta, session.target_grade, posterior_se(theta, irt_inputs))

    session.status = "completed"
    session.completed_at = now
    session.irt_theta = theta
    session.score = sum(1 for _, _, c in irt_inputs if c) / len(irt_inputs)
    session.grade_assigned = earned

    participant = await db.get(Participant, participant_id, with_for_update=True)
    decision = decide_grade(
        participant.assessed_grade if participant is not None else None, earned, session.target_grade, now)
    if participant is not None and decision.applied:
        participant.assessed_grade = decision.assessed_grade
        participant.assessed_at = now
        if decision.locked_until is not None:
            participant.grade_locked_until = decision.locked_until
    await db.flush()
    return session, decision


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
    ordered = [q_map[str(i)] for i in q_ids if str(i) in q_map]
    return session, ordered
