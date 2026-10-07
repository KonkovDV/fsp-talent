"""Grade test v2: adaptive sessions from parametric item families, per-specialization grade policy.

Flow: start → (serve item → answer)* → finalize. One item is on screen at a time; its right answer stays on
the server. The selector, stop rule and decision live in app.services.cat; this module stores sessions,
applies the grade policy, updates item statistics and quarantines leaked items.

Policy (TZ section 2, "Категория и грейд", and the Q&A with ФСП):
  * The grade comes only from the primary test of the specialization. A test built from a vacancy
    (flags["vacancy_id"]) shows topic results and confirms skills, but never changes the grade.
  * A test at grade G confirms G or nothing. A result confidently above the next cut
    (P(θ ≥ next cut) ≥ cat.RECOMMEND_NEXT_P) does not raise the grade: the session stores a recommendation
    to take a separate test at the next grade (flags["recommended_grade"]).
  * A test never lowers a confirmed grade. A failed attempt changes nothing.
  * Grades are confirmed per specialization: a backend confirmation says nothing about security.
  * Only an actual grade change starts the cooldown (GRADE_COOLDOWN_DAYS) for that specialization.
    Retakes of the same target are throttled separately (RETAKE_INTERVAL_DAYS); an abandoned or expired
    session counts as an attempt, otherwise the items could be previewed for free. A failed test at G does
    not burn the lower grade: a test at a lower grade is available at once (see retake_available_at).
  * A jury express session (flags mode "express") confirms nothing, starts no pause and stays out of search.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import random
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.items import TYPED_C, same_number, typed_answer
from app.items.families.concept_pools import idea_id
from app.items.registry import FAMILIES
from app.models.assessment import (
    GRADE_COOLDOWN_DAYS,
    GRADE_ORDER,
    SESSION_TTL_MINUTES,
    GradeConfirmation,
    ItemStat,
    TestSession,
    TestSessionItem,
)
from app.models.participant import Participant, Skill
from app.services import cat
from app.services.item_monitor import KeyStats, leave_family_out
from app.services.person_fit import LZ_FLAG, person_fit
from app.services.skills import normalize_skill

RETAKE_INTERVAL_DAYS = 7
TIME_LIMIT_S = {"code": 180, "concept": 75}
GRACE_S = 5
FAST_CORRECT_S = 4          # a right answer to a code item faster than this is flagged for review
PACE_REVIEW_FAST = 3        # this many fast right answers in one family mark the session for a look
# Session CUSUM by family. It does not quarantine a key and does not move the grade.
SHARE_REF = 0.55
SHARE_SLACK = 0.10
TIME_REF_S = 8.0
TIME_SLACK = 0.20
FAMILY_CUSUM_H = 1.6
SKILL_CONFIRM_SHARE = 0.75  # a tested skill counts as confirmed at ≥ 75 % right answers (≥ 3 items)
EXPOSURE_MIN_SESSIONS = 20


def note_pace(flags: dict, family_id: str, *, correct: bool, elapsed: float, kind: str) -> dict:
    """Count fast right answers per family. Three in one family ask for a look; the grade does not move."""
    flags = dict(flags)
    pace = {key: dict(value) for key, value in (flags.get("family_pace") or {}).items()}
    cell = dict(pace.get(family_id) or {"n": 0, "fast": 0})
    cell["n"] += 1
    if correct and kind == "code" and elapsed < FAST_CORRECT_S:
        cell["fast"] += 1
        flags["fast_correct"] = int(flags.get("fast_correct") or 0) + 1
    pace[family_id] = cell
    flags["family_pace"] = pace
    if cell["fast"] >= PACE_REVIEW_FAST:
        flags["pace_review"] = family_id
    return flags


def note_family_cusum(flags: dict, family_id: str, *, correct: bool, elapsed: float, kind: str) -> dict:
    """One-sided CUSUM of the right-answer share and of fast code answers, per family.

    The key-level CUSUM in the item monitor is a different signal and still decides quarantine.
    This one only asks for a look at the session.
    """
    flags = dict(flags)
    pace = {key: dict(value) for key, value in (flags.get("family_pace") or {}).items()}
    cell = dict(pace.get(family_id) or {})
    share = max(0.0, float(cell.get("share_cusum") or 0.0) + (int(correct) - SHARE_REF - SHARE_SLACK))
    time_cusum = float(cell.get("time_cusum") or 0.0)
    if kind == "code":
        excess = max(0.0, (TIME_REF_S - float(elapsed)) / TIME_REF_S)
        time_cusum = max(0.0, time_cusum + excess - TIME_SLACK)
    cell["share_cusum"] = round(share, 3)
    cell["time_cusum"] = round(time_cusum, 3)
    pace[family_id] = cell
    flags["family_pace"] = pace
    if cell["share_cusum"] >= FAMILY_CUSUM_H or cell["time_cusum"] >= FAMILY_CUSUM_H:
        flags["family_cusum_review"] = family_id
    return flags


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
    # first_confirmation | upgrade | confirmed_again | kept_higher_grade | not_passed | vacancy_test
    reason: str


def is_trial(flags: dict | None) -> bool:
    """A jury express session. It does not confirm a grade, start a pause or enter search."""
    return (flags or {}).get("mode") == "express"


def trial_decision() -> GradeDecision:
    return GradeDecision(None, False, False, None, "trial")


def decide_grade(current: str | None, earned: str | None, target_grade: str, now: datetime,
                 vacancy_test: bool = False) -> GradeDecision:
    """A test at target_grade confirms target_grade or nothing; a vacancy test confirms nothing."""
    if vacancy_test:
        return GradeDecision(current, False, False, None, "vacancy_test")
    if earned is None or not passed_target(earned, target_grade):
        return GradeDecision(current, False, False, None, "not_passed")
    earned = target_grade   # no automatic jump above the grade that was tested
    if current is None:
        # First confirmation is the baseline, not a change: it does not start the cooldown.
        return GradeDecision(earned, True, False, None, "first_confirmation")
    if GRADE_ORDER.index(earned) > GRADE_ORDER.index(current):
        return GradeDecision(earned, True, True, now + timedelta(days=GRADE_COOLDOWN_DAYS), "upgrade")
    if earned == current:
        return GradeDecision(current, False, False, None, "confirmed_again")
    return GradeDecision(current, False, False, None, "kept_higher_grade")


def recommended_grade(confirmed: str | None, outcome: cat.Outcome, target_grade: str,
                      vacancy_test: bool = False) -> str | None:
    """Grade worth a separate primary test after this session, or None.

    Primary test: the next grade when the result is confidently above its cut. Vacancy test: the target grade
    it passed (and the next one on a confident result), since only the primary test confirms a grade.
    Nothing at or below the grade already confirmed is recommended.
    """
    options = []
    if vacancy_test and outcome.passed:
        options.append(target_grade)
    if outcome.passed and outcome.recommend_next:
        options.append(outcome.recommend_next)
    floor = GRADE_ORDER.index(confirmed) if confirmed in GRADE_ORDER else -1
    above = [g for g in options if GRADE_ORDER.index(g) > floor]
    return max(above, key=GRADE_ORDER.index) if above else None


@dataclass(frozen=True)
class Attempt:
    """A finished or dropped attempt of one specialization and one kind (primary or vacancy test)."""
    target_grade: str
    completed_at: datetime
    failed: bool   # completed without passing the target; abandoned or expired attempts are not "failed"


def retake_available_at(attempts: list[Attempt], target_grade: str, now: datetime) -> datetime | None:
    """When a test at target_grade may be started again; None means now.

    The same grade can be retaken RETAKE_INTERVAL_DAYS after the last attempt at it. Stepping down after a
    failure is free: a failed attempt at a higher grade made after that attempt lifts the lock, so a candidate
    who failed middle can take junior at once even if a junior attempt was made a few days earlier.
    """
    since = now - timedelta(days=RETAKE_INTERVAL_DAYS)
    same = [a.completed_at for a in attempts if a.target_grade == target_grade and a.completed_at > since]
    if not same:
        return None
    last = max(same)
    rank = GRADE_ORDER.index(target_grade)
    if any(a.failed and a.completed_at > last and GRADE_ORDER.index(a.target_grade) > rank for a in attempts):
        return None
    return last + timedelta(days=RETAKE_INTERVAL_DAYS)


def is_vacancy_session(session: TestSession) -> bool:
    return bool((session.flags or {}).get("vacancy_id"))


def item_token(session_id: uuid.UUID, seq: int, item_id: uuid.UUID) -> str:
    msg = f"item:{session_id}:{seq}:{item_id}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]


def answer_mac(session_id: uuid.UUID, seq: int, correct_index: int, options: list) -> str:
    """Sign the key that was stored with the item. The browser never receives this value."""
    body = json.dumps(
        {"session": str(session_id), "seq": seq, "index": correct_index, "options": list(options)},
        ensure_ascii=False, separators=(",", ":"),
    )
    return hmac.new(settings.SECRET_KEY.encode(), f"answer:{body}".encode(), hashlib.sha256).hexdigest()


def answer_holds(stored: str | None, session_id: uuid.UUID, seq: int, correct_index: int, options: list) -> bool:
    """A row from before the mac existed is still scored. A row whose key was rewritten is not."""
    if not stored:
        return True
    return hmac.compare_digest(stored, answer_mac(session_id, seq, correct_index, options))


def scored_answer(holds: bool, right: bool, timed_out: bool) -> tuple[bool | None, bool]:
    """Return (is_correct, excluded). A key that does not match its mac does not move θ."""
    if not holds:
        return None, True
    return (not timed_out) and right, False


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
                                spec: str | None = None, vacancy_test: bool = False) -> datetime | None:
    """Retake lock for target_grade. Primary and vacancy tests are throttled separately: a vacancy test does
    not change the grade, so it must not block the primary test, and the other way round."""
    now = datetime.now(UTC)
    since = now - timedelta(days=RETAKE_INTERVAL_DAYS)
    kind = TestSession.flags.has_key("vacancy_id")
    not_trial = or_(TestSession.flags["mode"].astext.is_(None), TestSession.flags["mode"].astext != "express")
    query = select(TestSession.target_grade, TestSession.completed_at, TestSession.status,
                   TestSession.grade_assigned).where(
        TestSession.participant_id == participant_id,
        TestSession.status.in_(("completed", "abandoned", "expired")), TestSession.completed_at > since,
        kind if vacancy_test else ~kind, not_trial)
    if spec:
        query = query.where(TestSession.specialization == spec)
    attempts = [Attempt(target, done, status == "completed" and not passed_target(assigned, target))
                for target, done, status, assigned in await db.execute(query)]
    return retake_available_at(attempts, target_grade, now)


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


def _topic_shares(session: TestSession) -> dict[str, float] | None:
    shares = (session.flags or {}).get("topic_shares")
    return shares if isinstance(shares, dict) and shares else None


def build_state(spec: str, target: str, items: list[TestSessionItem], blocked: set[str] | None = None,
               blueprint: dict[str, float] | None = None) -> cat.State:
    """Rebuild the CAT state from answered items; items quarantined since they were served do not count."""
    blocked = blocked or set()
    state = cat.State(spec=spec, target=target, blueprint=blueprint)
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
                        code_language: str = "python", topic_shares: dict[str, float] | None = None,
                        vacancy_id: uuid.UUID | None = None, mode: str = "grade",
                        ) -> tuple[TestSession, TestSessionItem]:
    if target_grade not in GRADE_ORDER:
        raise ValueError(f"Invalid grade: {target_grade}")
    now = datetime.now(UTC)
    await db.execute(update(TestSession).where(
        TestSession.participant_id == participant_id, TestSession.status == "in_progress",
        TestSession.expires_at <= now).values(status="expired", completed_at=now))
    flags: dict = {"code_language": code_language}
    if mode == "express":
        flags["mode"] = "express"
    if topic_shares:
        flags["topic_shares"] = topic_shares
    if vacancy_id is not None:
        # A vacancy test: same items and scale, but it never changes the grade (see decide_grade).
        flags["vacancy_id"] = str(vacancy_id)
    ttl = cat.EXPRESS_MINUTES if mode == "express" else SESSION_TTL_MINUTES
    session = TestSession(
        participant_id=participant_id, target_grade=target_grade, discipline=spec, specialization=spec,
        engine="cat_v2", questions_json=[], seed=secrets.randbits(62), flags=flags,
        expires_at=now + timedelta(minutes=ttl),
    )
    prior = cat.evaluate(cat.State(spec=spec, target=target_grade, blueprint=topic_shares))
    session.p_pass, session.irt_theta, session.theta_se = prior.p_pass, prior.theta, prior.se
    db.add(session)
    await db.flush()
    bank = await bank_state(db)
    item = await serve_next(
        db, session, cat.State(spec=spec, target=target_grade, blueprint=topic_shares), bank, seq=1)
    return session, item


async def _seen_concepts(db: AsyncSession, session: TestSession) -> set[str]:
    """Wordings this candidate has already been shown, including other specializations.

    HTTP questions are shared, so a backend attempt counts for a later frontend attempt too.
    The current session is excluded: its items are already in the selector state.
    """
    flags = dict(session.flags or {})
    if "seen_concepts" not in flags:
        rows = await db.scalars(
            select(TestSessionItem.item_key)
            .join(TestSession, TestSession.id == TestSessionItem.session_id)
            .where(TestSession.participant_id == session.participant_id,
                   TestSession.id != session.id,
                   TestSessionItem.kind == "concept"))
        flags["seen_concepts"] = sorted(set(rows))
        session.flags = flags
    return set(flags["seen_concepts"])


async def serve_next(db: AsyncSession, session: TestSession, state: cat.State, bank: BankState,
                     seq: int) -> TestSessionItem:
    rng = random.Random(f"{session.seed}:{seq}")
    seen = await _seen_concepts(db, session)
    used_ideas = {found for key in state.keys_used if (found := idea_id(key))}
    forbidden = seen | state.keys_used | bank.blocked
    local_blocked = set(bank.blocked)
    item = None
    key = ""
    choice = None
    for _ in range(8):
        try:
            choice = cat.choose(state, rng, bank.offsets, bank.exposure, local_blocked)
        except LookupError as e:
            raise QuestionBankError(str(e)) from e
        fam = choice.family
        lang = (session.flags or {}).get("code_language", "python")
        try:
            if fam.kind == "concept":
                item = fam.generate(rng, choice.level, session.specialization,
                                    avoid=forbidden, used_ideas=used_ideas)
            else:
                extra = {"lang": lang} if lang in fam.languages and len(fam.languages) > 1 else {}
                item = fam.generate(rng, choice.level, session.specialization, **extra)
        except LookupError:
            local_blocked.add(cat.item_key(fam, choice.level))
            item = None
            continue
        key = item.static_key or cat.item_key(fam, choice.level)
        if item.static_key and key in forbidden:
            local_blocked.add(cat.item_key(fam, choice.level))
            item = None
            continue
        break
    if item is None or choice is None:
        raise QuestionBankError(f"no fresh item for {session.specialization}")
    fam = choice.family
    b = choice.b + (bank.offsets.get(key, 0.0) if item.static_key else 0.0)
    typed = typed_answer(fam.kind, item) is not None
    row = TestSessionItem(
        session_id=session.id, seq=seq, item_key=key, family_id=fam.id, level=choice.level, topic=fam.topic,
        kind=fam.kind, skills=list(fam.skills), stem=item.stem, code=item.code, language=item.language,
        options=item.options, correct_index=item.correct, explanation=item.explanation, typed=typed,
        a=choice.a, b=b, c=TYPED_C if typed else 1.0 / len(item.options),
        time_limit_s=cat.EXPRESS_ITEM_S if is_trial(session.flags) else TIME_LIMIT_S[fam.kind],
        served_at=datetime.now(UTC),
        answer_mac=answer_mac(session.id, seq, item.correct, item.options),
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
                      answer_index: int | None = None, answer_text: str | None = None,
                      ) -> tuple[TestSession, TestSessionItem | None, Finished | None]:
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
    # A malformed answer is rejected before it consumes the item.
    if current.typed:
        if not (answer_text or "").strip():
            raise SessionError("answer_required")
        current.answer_text = answer_text.strip()[:32]
        right = same_number(answer_text, current.options[current.correct_index])
    else:
        if answer_index is None or not 0 <= answer_index < len(current.options):
            raise SessionError("answer_required")
        current.answer_index = answer_index
        right = answer_index == current.correct_index
    elapsed = (now - current.served_at).total_seconds()
    current.answered_at = now
    current.timed_out = elapsed > current.time_limit_s + GRACE_S
    holds = answer_holds(current.answer_mac, session.id, current.seq, current.correct_index, current.options)
    current.is_correct, dropped = scored_answer(holds, right, current.timed_out)
    if dropped:
        current.excluded = True
    flags = dict(session.flags or {})
    if not holds:
        flags["integrity_review"] = True
    if current.timed_out:
        flags["timeouts"] = flags.get("timeouts", 0) + 1
    flags = note_pace(flags, current.family_id, correct=bool(current.is_correct), elapsed=elapsed, kind=current.kind)
    flags = note_family_cusum(
        flags, current.family_id, correct=bool(current.is_correct), elapsed=elapsed, kind=current.kind)
    session.flags = flags
    await db.flush()

    bank = await bank_state(db)
    state = build_state(session.specialization, session.target_grade, items, bank.blocked,
                        _topic_shares(session))
    verdict = cat.evaluate(state, item_limit=cat.EXPRESS_ITEMS if is_trial(session.flags) else None)
    session.p_pass, session.p_upgrade = verdict.p_pass, verdict.p_upgrade
    session.irt_theta, session.theta_se = verdict.theta, verdict.se
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
    state = build_state(session.specialization, session.target_grade, items, bank.blocked,
                        _topic_shares(session))
    outcome = cat.decide(state)
    answered = [it for it in items if it.is_correct is not None and not it.excluded]
    trial = is_trial(session.flags)
    session.status, session.completed_at, session.stop_reason = "completed", now, stop_reason
    session.irt_theta, session.theta_se = outcome.theta, outcome.se
    session.p_pass, session.p_upgrade = outcome.p_pass, outcome.p_upgrade
    session.items_count = len(answered)
    session.score = sum(1 for it in answered if it.is_correct) / len(answered) if answered else 0.0
    session.grade_assigned = None if trial else outcome.earned

    participant = await db.get(Participant, session.participant_id, with_for_update=True)
    vacancy_test = is_vacancy_session(session)
    if trial:
        # Shown to the person who sat it. No grade, no pause, no skill confirmation, no leak counters:
        # a short jury pass must not move the bank or the category.
        decision = trial_decision()
        confirmed: list[tuple[str, float]] = []
        conf = None
    else:
        conf = await confirmation(db, session.participant_id, session.specialization)
        decision = decide_grade(conf.grade if conf else None, outcome.earned if outcome.passed else None,
                                session.target_grade, now, vacancy_test)
    if not trial and decision.applied:
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
    if participant is not None and not trial:
        await sync_assessed_grade(db, participant)
    flags = dict(session.flags or {})
    flags["outcome"] = decision.reason
    if len(answered) >= cat.MIN_ITEMS and not trial:
        lz, lz_star = person_fit(
            [cat.Response(it.a, it.b, it.c, bool(it.is_correct)) for it in answered], outcome.theta)
        flags["person_fit"] = {"lz": round(lz, 3), "lz_star": round(lz_star, 3), "review": lz_star < LZ_FLAG}
    recommend = recommended_grade(decision.assessed_grade, outcome, session.target_grade, vacancy_test)
    if recommend:
        flags["recommended_grade"] = recommend
    session.flags = flags

    if not trial:
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
                                 expected=0.0, variance=0.0, sessions=0, b_offset=0.0, status="active", z=0.0,
                                 cusum=0.0)
            db.add(rows[key])
        rows[key].sessions += 1
    expected = leave_family_out(
        [(it.item_key, it.family_id, it.a, it.b, it.c, bool(it.is_correct)) for it in answered], prior_mean)
    for key, p, ok in expected:
        r = rows[key]
        st = KeyStats(r.n, r.correct, r.expected, r.variance, r.cusum or 0.0)
        st.add(p, ok)
        r.n, r.correct, r.expected, r.variance, r.z, r.cusum = (
            st.n, st.correct, st.expected, st.variance, st.z, st.cusum)
        r.updated_at = now
        if (st.alarm or st.cusum_alarm) and r.status == "active":
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
                         trust_level="test_confirmed", confirmed=True, confirmed_at=now))
        else:
            if row.trust_level != "test_confirmed" or row.confirmed_at is None:
                row.confirmed_at = now
            row.trust_level, row.source_quote, row.confirmed = "test_confirmed", quote, True
    return confirmed


def family_title(family_id: str) -> str:
    fam = FAMILIES.get(family_id)
    return fam.title if fam else family_id
