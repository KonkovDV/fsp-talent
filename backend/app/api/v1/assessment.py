"""Grade test API (v2, adaptive). One item at a time; right answers stay on the server until the end.

GET  /assessment/blueprint            - what a test of each specialization consists of (public)
POST /assessment/start                - start a session, returns the first item
GET  /assessment/active               - resume the running session after a reload
GET  /assessment/{id}                 - session state: current item or the result
POST /assessment/{id}/answer          - answer the current item (item_token + option index)
POST /assessment/{id}/abandon         - stop; counts as an attempt
GET  /assessment/{id}/review          - after the end: items with right answers and explanations
GET  /assessment/cooldown             - retake / upgrade locks
GET  /assessment/history              - past sessions
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant
from app.api.errors import ApiError
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.items.families.langs import LANGUAGE_LABELS
from app.items.registry import BLUEPRINTS, CONCEPT_MAX_SHARE, families_for
from app.models import Participant, Vacancy
from app.models.assessment import GRADE_ORDER, TestSession, TestSessionItem
from app.services import cat
from app.services.assessment import (
    Finished,
    QuestionBankError,
    SessionError,
    abandon,
    answer_item,
    check_cooldown,
    check_retake_interval,
    confirmation,
    family_title,
    get_active_session,
    item_token,
    session_items,
    start_session,
)
from app.services.profile import rebuild_profile
from app.services.survey import SPECIALIZATIONS
from app.services.vacancy_exam import form_exam

router = APIRouter(prefix="/assessment", tags=["assessment"])

Grade = Literal["junior", "middle", "senior", "lead"]
TOPIC_LABELS = {"python": "Python", "sql": "SQL", "algorithms": "Алгоритмы", "javascript": "JavaScript",
                "security": "Безопасность", "network": "Сети", "ml": "Машинное обучение",
                "embedded": "Встраиваемые системы", "concept": "Понимание"}


class StartIn(BaseModel):
    target_grade: Grade
    specialization: str | None = Field(None, description="По умолчанию — специализация из опроса")
    code_language: Literal["python", "javascript", "go", "java"] = Field(
        "python", description="Язык, на котором показывать задания на чтение кода")
    vacancy_id: uuid.UUID | None = Field(None, description="Собрать темы теста из этой вакансии")


class VacancyExamIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field("", max_length=4000)
    skills: list[str] = Field(default_factory=list, max_length=30)
    role: str | None = None
    grade: Grade | None = None


class AnswerIn(BaseModel):
    item_token: str = Field(min_length=16, max_length=64)
    answer_index: int = Field(ge=0, le=9)


class OptionOut(BaseModel):
    index: int
    text: str


class ItemOut(BaseModel):
    token: str
    seq: int
    stem: str
    code: str | None
    language: str | None
    options: list[OptionOut]
    topic: str
    topic_label: str
    family_title: str
    kind: str
    time_limit_s: int
    served_at: str


class SkillOut(BaseModel):
    name: str
    share: float


class TopicOut(BaseModel):
    topic: str
    label: str
    answered: int
    correct: int


class ResultOut(BaseModel):
    outcome: str        # first_confirmation | upgrade | confirmed_again | kept_higher_grade | not_passed
    passed: bool
    upgraded: bool
    earned_grade: str | None
    confirmed_grade: str | None
    p_pass: float
    p_upgrade: float | None
    theta: float
    se: float
    items_count: int
    score: float
    stop_reason: str | None
    grade_locked_until: str | None
    confirmed_skills: list[SkillOut]
    topics: list[TopicOut]
    excluded_items: int


class ProgressOut(BaseModel):
    answered: int
    min_items: int = cat.MIN_ITEMS
    max_items: int = cat.MAX_ITEMS
    p_pass: float | None = None


class SessionOut(BaseModel):
    session_id: str
    status: str
    specialization: str | None
    target_grade: str
    expires_at: str
    progress: ProgressOut
    item: ItemOut | None = None
    result: ResultOut | None = None


def _item_out(session_id: uuid.UUID, it: TestSessionItem) -> ItemOut:
    return ItemOut(
        token=item_token(session_id, it.seq, it.id), seq=it.seq, stem=it.stem, code=it.code, language=it.language,
        options=[OptionOut(index=i, text=t) for i, t in enumerate(it.options)], topic=it.topic,
        topic_label=TOPIC_LABELS.get(it.topic, it.topic), family_title=family_title(it.family_id), kind=it.kind,
        time_limit_s=it.time_limit_s, served_at=it.served_at.isoformat(),
    )


def _result_from_session(session: TestSession, items: list[TestSessionItem], confirmed: str | None,
                         reason: str | None = None, locked: str | None = None,
                         skills: list[tuple[str, float]] | None = None) -> ResultOut:
    answered = [it for it in items if it.is_correct is not None and not it.excluded]
    topics: dict[str, list[int]] = {}
    for it in answered:
        t = topics.setdefault(it.topic, [0, 0])
        t[0] += 1
        t[1] += int(bool(it.is_correct))
    passed = session.grade_assigned is not None and \
        GRADE_ORDER.index(session.grade_assigned) >= GRADE_ORDER.index(session.target_grade)
    upgraded = passed and session.grade_assigned != session.target_grade
    return ResultOut(
        outcome=reason or ("passed" if passed else "not_passed"), passed=passed, upgraded=upgraded,
        earned_grade=session.grade_assigned, confirmed_grade=confirmed,
        p_pass=round(session.p_pass or 0.0, 3),
        p_upgrade=round(session.p_upgrade, 3) if session.p_upgrade is not None else None,
        theta=round(session.irt_theta or 0.0, 3), se=round(session.theta_se or 0.0, 3),
        items_count=session.items_count or len(answered), score=round(session.score or 0.0, 3),
        stop_reason=session.stop_reason, grade_locked_until=locked,
        confirmed_skills=[SkillOut(name=n, share=round(v, 2)) for n, v in (skills or [])],
        topics=[TopicOut(topic=k, label=TOPIC_LABELS.get(k, k), answered=v[0], correct=v[1])
                for k, v in sorted(topics.items())],
        excluded_items=sum(1 for it in items if it.excluded),
    )


def _session_out(session: TestSession, items: list[TestSessionItem], result: ResultOut | None = None) -> SessionOut:
    current = items[-1] if items and items[-1].answered_at is None and session.status == "in_progress" else None
    answered = sum(1 for it in items if it.answered_at is not None)
    return SessionOut(
        session_id=str(session.id), status=session.status, specialization=session.specialization,
        target_grade=session.target_grade, expires_at=session.expires_at.isoformat(),
        progress=ProgressOut(answered=answered), item=_item_out(session.id, current) if current else None,
        result=result,
    )


async def _finished_result(db: AsyncSession, session: TestSession, items: list[TestSessionItem],
                           fin: Finished | None = None) -> ResultOut:
    conf = await confirmation(db, session.participant_id, session.specialization)
    if fin is not None:
        return _result_from_session(
            session, items, fin.decision.assessed_grade, fin.decision.reason,
            fin.decision.locked_until.isoformat() if fin.decision.locked_until else None, fin.confirmed_skills)
    return _result_from_session(session, items, conf.grade if conf else None,
                                locked=conf.locked_until.isoformat() if conf and conf.locked_until else None)


def _raise(e: SessionError):
    if e.code == "not_found":
        raise ApiError(404, "not_found", "Сессия не найдена") from e
    status_code = 410 if e.code == "session_expired" else 409
    raise ApiError(status_code, e.code) from e


@router.get("/blueprint")
async def blueprint():
    """Test structure per specialization: topics, shares and item families. Nothing here helps to cheat."""
    return {
        "min_items": cat.MIN_ITEMS, "max_items": cat.MAX_ITEMS, "pass_probability": cat.PASS_P,
        "code_languages": LANGUAGE_LABELS,
        "upgrade_probability": cat.UPGRADE_P, "concept_max_share": CONCEPT_MAX_SHARE,
        "cuts": cat.CUTS,
        "specializations": {
            spec: {"label": SPECIALIZATIONS[spec],
                   "topics": [{"topic": t, "label": TOPIC_LABELS.get(t, t), "share": w} for t, w in topics.items()],
                   "families": [{"id": f.id, "title": f.title, "kind": f.kind} for f in families_for(spec)]}
            for spec, topics in BLUEPRINTS.items()
        },
    }


@router.post("/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def start_test(body: StartIn, current: dict = Depends(get_current_participant),
                     db: AsyncSession = Depends(get_db)):
    participant_id = uuid.UUID(current["sub"])
    participant = await db.get(Participant, participant_id)
    if participant is None:
        raise ApiError(404, "not_found", "Профиль не найден")
    spec = body.specialization or participant.specialization
    topic_shares = None
    if body.vacancy_id is not None:
        vacancy = await db.get(Vacancy, body.vacancy_id)
        if vacancy is None or not vacancy.is_open:
            raise ApiError(404, "not_found", "Вакансия не найдена")
        exam = form_exam(vacancy.title, vacancy.description or "", list(vacancy.skills or []),
                         vacancy.role, vacancy.grade)
        spec = exam["specialization"]
        topic_shares = exam["topic_shares"]
    if spec not in BLUEPRINTS:
        raise ApiError(422, "survey_required")
    if await too_many(f"assessment_start:{participant_id}", limit=3, window_seconds=3600):
        raise ApiError(429, "rate_limited", "Не больше трёх попыток в час")
    locked = await check_cooldown(db, participant_id, spec)
    conf = await confirmation(db, participant_id, spec)
    if locked and conf and GRADE_ORDER.index(body.target_grade) > GRADE_ORDER.index(conf.grade):
        raise ApiError(429, "grade_locked", f"Повышение грейда доступно после {locked:%d.%m.%Y}",
                       details={"locked_until": locked.isoformat()})
    retake = await check_retake_interval(db, participant_id, body.target_grade, spec)
    if retake:
        raise ApiError(429, "retake_cooldown", f"Пересдача на этот грейд доступна после {retake:%d.%m.%Y}",
                       details={"retake_at": retake.isoformat()})
    existing = await get_active_session(db, participant_id)
    if existing and existing.expires_at > datetime.now(UTC):
        raise ApiError(409, "conflict", "Уже есть незавершённый тест", details={"session_id": str(existing.id)})
    try:
        session, item = await start_session(
            db, participant_id, spec, body.target_grade, body.code_language, topic_shares)
        await db.commit()
    except QuestionBankError as e:
        raise ApiError(503, "question_bank_empty") from e
    except IntegrityError as e:
        await db.rollback()
        raise ApiError(409, "conflict", "Уже есть незавершённый тест") from e
    return _session_out(session, [item])


@router.get("/active", response_model=SessionOut)
async def active(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    session = await get_active_session(db, uuid.UUID(current["sub"]))
    if session is None or session.expires_at <= datetime.now(UTC):
        raise ApiError(404, "not_found", "Нет незавершённого теста")
    return _session_out(session, await session_items(db, session.id))


@router.get("/cooldown")
async def cooldown_status(specialization: str | None = None, current: dict = Depends(get_current_participant),
                          db: AsyncSession = Depends(get_db)):
    locked = await check_cooldown(db, uuid.UUID(current["sub"]), specialization)
    return {"locked": locked is not None, "locked_until": locked.isoformat() if locked else None}


@router.get("/history")
async def session_history(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                          current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(
        select(TestSession).where(TestSession.participant_id == uuid.UUID(current["sub"]))
        .order_by(desc(TestSession.started_at)).limit(limit).offset(offset)))
    return {"items": [{
        "session_id": str(s.id), "status": s.status, "specialization": s.specialization,
        "target_grade": s.target_grade, "grade_assigned": s.grade_assigned, "score": s.score,
        "p_pass": s.p_pass, "items_count": s.items_count, "stop_reason": s.stop_reason,
        "started_at": s.started_at.isoformat(),
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
    } for s in rows], "limit": limit, "offset": offset}


async def _own(db: AsyncSession, session_id: uuid.UUID, current: dict) -> TestSession:
    session = await db.get(TestSession, session_id)
    if session is None or session.participant_id != uuid.UUID(current["sub"]) or session.engine != "cat_v2":
        raise ApiError(404, "not_found", "Сессия не найдена")
    return session


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: uuid.UUID, current: dict = Depends(get_current_participant),
                      db: AsyncSession = Depends(get_db)):
    session = await _own(db, session_id, current)
    items = await session_items(db, session.id)
    result = await _finished_result(db, session, items) if session.status == "completed" else None
    return _session_out(session, items, result)


@router.post("/{session_id}/answer", response_model=SessionOut)
async def answer(session_id: uuid.UUID, body: AnswerIn, current: dict = Depends(get_current_participant),
                 db: AsyncSession = Depends(get_db)):
    try:
        session, nxt, fin = await answer_item(db, session_id, uuid.UUID(current["sub"]), body.item_token,
                                              body.answer_index)
    except SessionError as e:
        await db.commit()   # an expired session is stored as expired
        _raise(e)
    except QuestionBankError as e:
        raise ApiError(503, "question_bank_empty") from e
    result = None
    if fin is not None:
        participant = await db.get(Participant, session.participant_id)
        if participant is not None:
            await rebuild_profile(db, participant)
    await db.commit()
    items = await session_items(db, session.id)
    if fin is not None:
        result = await _finished_result(db, session, items, fin)
    return _session_out(session, items, result)


@router.post("/{session_id}/abandon", response_model=SessionOut)
async def abandon_session(session_id: uuid.UUID, current: dict = Depends(get_current_participant),
                          db: AsyncSession = Depends(get_db)):
    try:
        session = await abandon(db, session_id, uuid.UUID(current["sub"]))
    except SessionError as e:
        _raise(e)
    await db.commit()
    return _session_out(session, await session_items(db, session.id))


@router.get("/{session_id}/review")
async def review(session_id: uuid.UUID, current: dict = Depends(get_current_participant),
                 db: AsyncSession = Depends(get_db)):
    """Parametric items are shown with answers: the next session gets different ones. Static concept items
    show only whether the answer was right, so the finite pool does not leak."""
    session = await _own(db, session_id, current)
    if session.status == "in_progress":
        raise ApiError(409, "conflict", "Разбор доступен после окончания теста")
    out = []
    for it in await session_items(db, session.id):
        static = it.kind == "concept"
        out.append({
            "seq": it.seq, "topic": it.topic, "topic_label": TOPIC_LABELS.get(it.topic, it.topic),
            "family_title": family_title(it.family_id), "level": it.level, "stem": it.stem, "code": it.code,
            "language": it.language, "options": it.options, "your_answer": it.answer_index,
            "correct": it.is_correct, "timed_out": it.timed_out, "excluded": it.excluded,
            "right_answer": None if static else it.correct_index,
            "explanation": None if static else it.explanation,
        })
    return {"session_id": str(session.id), "items": out}
