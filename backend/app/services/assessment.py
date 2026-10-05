"""Grade test v2: adaptive sessions from parametric item families, per-specialization grade policy.

Flow: start → (serve item → answer)* → finalize. One item is on screen at a time; its right answer stays on
the server. The selector, stop rule and decision live in app.services.cat; this module stores sessions,
applies the grade policy, updates item statistics and quarantines leaked items.

Policy (TZ section 2, "Категория и грейд"):
  * A test never lowers a confirmed grade. A failed attempt changes nothing; the candidate may take a test
    one level lower instead.
  * A confident result raises the grade one level above the target: P(θ ≥ next cut) ≥ cat.UPGRADE_P.
  * Grades are confirmed per specialization: a backend confirmation says nothing about security.
  * Only an actual grade change starts the cooldown (GRADE_COOLDOWN_DAYS) for that specialization.
    Retakes of the same target are throttled separately (RETAKE_INTERVAL_DAYS); an abandoned or expired
    session counts as an attempt, otherwise the items could be previewed for free.
"""
from __future__ import annotations

import hashlib
import hmac
import random
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.items.registry import FAMILIES
from app.models.assessment import (
    GRADE_COOLDOWN_DAYS,
    GRADE_ORDER,
    GradeConfirmation,
    ItemStat,
    TestSession,
    TestSessionItem,
)
from app.models.participant import Participant, Skill
from app.services import cat
from app.services.item_monitor import KeyStats, leave_family_out
from app.services.skills import normalize_skill

RETAKE_INTERVAL_DAYS = 7
SESSION_TTL_MINUTES = 40
TIME_LIMIT_S = {"code": 180, "concept": 75}
GRACE_S = 5
FAST_CORRECT_S = 4          # a right answer to a code item faster than this is flagged for review
SKILL_CONFIRM_SHARE = 0.75  # a tested skill counts as confirmed at ≥ 75 % right answers (≥ 3 items)
EXPOSURE_MIN_SESSIONS = 20


class QuestionBankError(RuntimeError):
    """No family can serve an item for this specialization."""


class SessionError(RuntimeError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


# ── grade policy (pure) ─────────────────────────────────────────────────────

def passed_target(earned: str | None, target_grade: str) -> bool:
    return earned is not None and GRADE_ORDER.index(earned) >= GRADE_ORDER.index(target_grade)


@dataclass(frozen=True)
class GradeDecision:
    """What a completed session does to the confirmed grade of its specialization."""
    assessed_grade: str | None
    applied: bool
    upgraded: bool
    locked_until: datetime | None
    reason: str   # first_confirmation | upgrade | confirmed_again | kept_higher_grade | not_passed


def decide_grade(current: str | None, earned: str | None, target_grade: str, now: datetime) -> GradeDecision:
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


def item_token(session_id: uuid.UUID, seq: int, item_id: uuid.UUID) -> str:
    msg = f"item:{session_id}:{seq}:{item_id}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]


# ── lookups ─────────────────────────────────────────────────────────────────

async def confirmation(db: AsyncSession, participant_id: uuid.UUID, spec: str) -> GradeConfirmation | None:
    return await db.scalar(select(GradeConfirmation).where(
        GradeConfirmation.participant_id == participant_id, GradeConfirmation.specialization == spec))


async def check_cooldown(db: AsyncSession, participant_id: uuid.UUID, spec: str | None = None) -> datetime | None:
    query = select(func.max(GradeConfirmation.locked_until)).where(
        GradeConfirmation.participant_id == participant_id)
    if spec:
        query = query.where(GradeConfirmation.specialization == spec)
    locked = await db.scalar(query)
    return locked if locked and locked > datetime.now(UTC) else None


async def check_retake_interval(db: AsyncSession, participant_id: uuid.UUID, target_grade: str,
                                spec: str | None = None) -> datetime | None:
    since = datetime.now(UTC) - timedelta(days=RETAKE_INTERVAL_DAYS)
    query = select(func.max(TestSession.completed_at)).where(
        TestSession.participant_id == participant_id, TestSession.target_grade == target_grade,
        TestSession.status.in_(("completed", "abandoned", "expired")), TestSession.completed_at > since)
    if spec:
        query = query.where(TestSession.specialization == spec)
    last = await db.scalar(query)
    return last + timedelta(days=RETAKE_INTERVAL_DAYS) if last else None


async def get_active_session(db: AsyncSession, participant_id: uuid.UUID) -> TestSession | None:
    return await db.scalar(select(TestSession).where(and_(
        TestSession.participant_id == participant_id, TestSession.status == "in_progress")))


async def session_items(db: AsyncSession, session_id: uuid.UUID) -> list[TestSessionItem]:
    return list(await db.scalars(
        select(TestSessionItem).where(TestSessionItem.session_id == session_id).order_by(TestSessionItem.seq)))


@dataclass
class BankState:
    offsets: dict[str, float]
    exposure: dict[str, float]
    blocked: set[str]


async def bank_state(db: AsyncSession) -> BankState:
    rows = list(await db.scalars(select(ItemStat)))
    total = await db.scalar(select(func.count()).select_from(TestSession).where(
        TestSession.engine == "cat_v2", TestSession.status == "completed")) or 0
    exposure = {r.item_key: r.sessions / total for r in rows} if total >= EXPOSURE_MIN_SESSIONS else {}
    return BankState(offsets={r.item_key: r.b_offset for r in rows if r.b_offset},
                     exposure=exposure, blocked={r.item_key for r in rows if r.status == "quarantined"})


def build_state(spec: str, target: str, items: list[TestSessionItem], blocked: set[str] | None = None) -> cat.State:
    """Rebuild the CAT state from answered items; items quarantined since they were served do not count."""
    blocked = blocked or set()
    state = cat.State(spec=spec, target=target)
    for it in items:
        state.families_used[it.family_id] += 1
        state.topics_used[it.topic] += 1
        state.concept_used += it.kind == "concept"
        state.keys_used.add(it.item_key)
        if it.is_correct is None or it.item_key in blocked or it.excluded:
            continue
        state.responses.append(cat.Response(it.a, it.b, it.c, bool(it.is_correct)))
    return state


# ── session flow ────────────────────────────────────────────────────────────

async def start_session(db: AsyncSession, participant_id: uuid.UUID, spec: str, target_grade: str,
                        code_language: str = "python") -> tuple[TestSession, TestSessionItem]:
    if target_grade not in GRADE_ORDER:
        raise ValueError(f"Invalid grade: {target_grade}")
    now = datetime.now(UTC)
    await db.execute(update(TestSession).where(
        TestSession.participant_id == participant_id, TestSession.status == "in_progress",
        TestSession.expires_at <= now).values(status="expired", completed_at=now))
    session = TestSession(
        participant_id=participant_id, target_grade=target_grade, discipline=spec, specialization=spec,
        engine="cat_v2", questions_json=[], seed=secrets.randbits(62), flags={"code_language": code_language},
        expires_at=now + timedelta(minutes=SESSION_TTL_MINUTES),
    )
    db.add(session)
    await db.flush()
    bank = await bank_state(db)
    item = await serve_next(db, session, cat.State(spec=spec, target=target_grade), bank, seq=1)
    return session, item


async def serve_next(db: AsyncSession, session: TestSession, state: cat.State, bank: BankState,
                     seq: int) -> TestSessionItem:
    rng = random.Random(f"{session.seed}:{seq}")
    try:
        choice = cat.choose(state, rng, bank.offsets, bank.exposure, bank.blocked)
    except LookupError as e:
        raise QuestionBankError(str(e)) from e
    fam = choice.family
    lang = (session.flags or {}).get("code_language", "python")
    extra = {"lang": lang} if lang in fam.languages and len(fam.languages) > 1 else {}
    for _ in range(8):
        item = fam.generate(rng, choice.level, session.specialization, **extra)
        key = item.static_key or cat.item_key(fam, choice.level)
        if key not in bank.blocked and key not in state.keys_used:
            break
    b = choice.b + (bank.offsets.get(key, 0.0) if item.static_key else 0.0)
    row = TestSessionItem(
        session_id=session.id, seq=seq, item_key=key, family_id=fam.id, level=choice.level, topic=fam.topic,
        kind=fam.kind, skills=list(fam.skills), stem=item.stem, code=item.code, language=item.language,
        options=item.options, correct_index=item.correct, explanation=item.explanation,
        a=choice.a, b=b, c=1.0 / len(item.options), time_limit_s=TIME_LIMIT_S[fam.kind],
        served_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row


@dataclass
class Finished:
    session: TestSession
    decision: GradeDecision
    outcome: cat.Outcome
    confirmed_skills: list[tuple[str, float]]
    topics: dict[str, tuple[int, int]]


async def answer_item(db: AsyncSession, session_id: uuid.UUID, participant_id: uuid.UUID, token: str,
                      answer_index: int) -> tuple[TestSession, TestSessionItem | None, Finished | None]:
    session = await db.get(TestSession, session_id, with_for_update=True)
    if session is None or session.participant_id != participant_id or session.engine != "cat_v2":
        raise SessionError("not_found")
    if session.status != "in_progress":
        raise SessionError("session_closed")
    now = datetime.now(UTC)
    if session.expires_at <= now:
        session.status, session.completed_at, session.stop_reason = "expired", now, "expired"
        await db.flush()
        raise SessionError("session_expired")
    items = await session_items(db, session.id)
    current = items[-1] if items else None
    if current is None or current.answered_at is not None or not hmac.compare_digest(
            token, item_token(session.id, current.seq, current.id)):
        raise SessionError("item_token_invalid")
    elapsed = (now - current.served_at).total_seconds()
    current.answered_at = now
    current.answer_index = answer_index
    current.timed_out = elapsed > current.time_limit_s + GRACE_S
    current.is_correct = (not current.timed_out) and answer_index == current.correct_index
    flags = dict(session.flags or {})
    if current.timed_out:
        flags["timeouts"] = flags.get("timeouts", 0) + 1
    if current.is_correct and current.kind == "code" and elapsed < FAST_CORRECT_S:
        flags["fast_correct"] = flags.get("fast_correct", 0) + 1
    session.flags = flags
    await db.flush()

    bank = await bank_state(db)
    state = build_state(session.specialization, session.target_grade, items, bank.blocked)
    verdict = cat.evaluate(state)
    if verdict.done:
        finished = await finalize(db, session, items, bank, verdict.stop_reason or "decided")
        return session, None, finished
    try:
        nxt = await serve_next(db, session, state, bank, seq=current.seq + 1)
    except QuestionBankError:
        finished = await finalize(db, session, items, bank, "bank_exhausted")
        return session, None, finished
    return session, nxt, None


async def abandon(db: AsyncSession, session_id: uuid.UUID, participant_id: uuid.UUID) -> TestSession:
    session = await db.get(TestSession, session_id, with_for_update=True)
    if session is None or session.participant_id != participant_id:
        raise SessionError("not_found")
    if session.status != "in_progress":
        raise SessionError("session_closed")
    session.status, session.completed_at, session.stop_reason = "abandoned", datetime.now(UTC), "abandoned"
    await db.flush()
    return session


async def finalize(db: AsyncSession, session: TestSession, items: list[TestSessionItem], bank: BankState,
                   stop_reason: str) -> Finished:
    now = datetime.now(UTC)
    for it in items:
        if it.item_key in bank.blocked:
            it.excluded = True
    state = build_state(session.specialization, session.target_grade, items, bank.blocked)
    outcome = cat.decide(state)
    answered = [it for it in items if it.is_correct is not None and not it.excluded]
    session.status, session.completed_at, session.stop_reason = "completed", now, stop_reason
    session.irt_theta, session.theta_se = outcome.theta, outcome.se
    session.p_pass, session.p_upgrade = outcome.p_pass, outcome.p_upgrade
    session.items_count = len(answered)
    session.score = sum(1 for it in answered if it.is_correct) / len(answered) if answered else 0.0
    session.grade_assigned = outcome.earned

    participant = await db.get(Participant, session.participant_id, with_for_update=True)
    conf = await confirmation(db, session.participant_id, session.specialization)
    decision = decide_grade(conf.grade if conf else None, outcome.earned if outcome.passed else None,
                            session.target_grade, now)
    if decision.applied:
        if conf is None:
            conf = GradeConfirmation(participant_id=session.participant_id, specialization=session.specialization,
                                     grade=decision.assessed_grade)
            db.add(conf)
        conf.grade, conf.p_pass = decision.assessed_grade, outcome.p_pass
        conf.theta, conf.se = outcome.theta, outcome.se
        conf.session_id, conf.confirmed_at = session.id, now
        if decision.locked_until is not None:
            conf.locked_until = decision.locked_until
        await db.flush()
    if participant is not None:
        await sync_assessed_grade(db, participant)

    await _update_item_stats(db, answered, cat.CUTS[session.target_grade])
    confirmed = await _confirm_skills(db, session, answered, now)
    topics: dict[str, tuple[int, int]] = {}
    for it in answered:
        n, right = topics.get(it.topic, (0, 0))
        topics[it.topic] = (n + 1, right + int(bool(it.is_correct)))
    await db.flush()
    return Finished(session, decision, outcome, confirmed, topics)


async def sync_assessed_grade(db: AsyncSession, participant: Participant) -> None:
    """The profile shows the grade confirmed for the specialization the candidate chose in the survey."""
    if participant.specialization:
        conf = await confirmation(db, participant.id, participant.specialization)
    else:
        conf = await db.scalar(select(GradeConfirmation).where(
            GradeConfirmation.participant_id == participant.id).order_by(GradeConfirmation.confirmed_at.desc()))
    participant.assessed_grade = conf.grade if conf else None
    participant.assessed_at = conf.confirmed_at if conf else None
    participant.grade_locked_until = conf.locked_until if conf else None


async def _update_item_stats(db: AsyncSession, answered: list[TestSessionItem], prior_mean: float) -> None:
    keys = {it.item_key for it in answered}
    if not keys:
        return
    rows = {r.item_key: r for r in await db.scalars(
        select(ItemStat).where(ItemStat.item_key.in_(keys)).with_for_update())}
    now = datetime.now(UTC)
    for key in keys:
        if key not in rows:
            sample = next(it for it in answered if it.item_key == key)
            rows[key] = ItemStat(item_key=key, family_id=sample.family_id, level=sample.level, n=0, correct=0,
                                 expected=0.0, variance=0.0, sessions=0, b_offset=0.0, status="active", z=0.0)
            db.add(rows[key])
        rows[key].sessions += 1
    expected = leave_family_out(
        [(it.item_key, it.family_id, it.a, it.b, it.c, bool(it.is_correct)) for it in answered], prior_mean)
    for key, p, ok in expected:
        r = rows[key]
        st = KeyStats(r.n, r.correct, r.expected, r.variance)
        st.add(p, ok)
        r.n, r.correct, r.expected, r.variance, r.z = st.n, st.correct, st.expected, st.variance, st.z
        r.updated_at = now
        if st.alarm and r.status == "active":
            r.status, r.quarantined_at = "quarantined", now


async def _confirm_skills(db: AsyncSession, session: TestSession, answered: list[TestSessionItem],
                          now: datetime) -> list[tuple[str, float]]:
    """Skills the test confirmed (≥ 75 % right on ≥ 3 items). Declared skills stay declarations."""
    scores = cat.skill_scores([(tuple(it.skills), bool(it.is_correct)) for it in answered])
    confirmed = []
    for raw, share in scores.items():
        name = normalize_skill(raw)
        if not name or share < SKILL_CONFIRM_SHARE:
            continue
        confirmed.append((name, share))
        quote = f"Тест {now:%d.%m.%Y}: {round(share * 100)}% верных ответов"
        row = await db.scalar(select(Skill).where(Skill.participant_id == session.participant_id, Skill.name == name))
        if row is None:
            db.add(Skill(participant_id=session.participant_id, name=name, raw_name=raw, source_quote=quote,
                         trust_level="test_confirmed", confirmed=True))
        else:
            row.trust_level, row.source_quote, row.confirmed = "test_confirmed", quote, True
    return confirmed


def family_title(family_id: str) -> str:
    fam = FAMILIES.get(family_id)
    return fam.title if fam else family_id
