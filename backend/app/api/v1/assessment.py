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

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant
from app.api.errors import ApiError
from app.core.config import settings
from app.core.database import get_db
from app.core.idempotency import (
    IdempotencyConflict,
    IdempotencyUnavailable,
    fingerprint,
    idem_abort,
    idem_begin,
    idem_finish,
)
from app.core.ratelimit import too_many
from app.items.families.langs import LANGUAGE_LABELS
from app.items.registry import BLUEPRINTS, CONCEPT_MAX_SHARE, families_for
from app.models import Participant, PracticeAttempt, Vacancy
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
from app.services.matching import wilson_lower
from app.services.practice import (
    answer_practice,
    public_attempt,
    same_practice_request,
    start_practice,
    weekly_task,
)
from app.services.profile import rebuild_profile
from app.services.survey import SPECIALIZATIONS
from app.services.vacancy_exam import form_exam

router = APIRouter(prefix="/assessment", tags=["assessment"])

Grade = Literal["intern", "junior", "middle", "senior", "lead"]
TOPIC_LABELS = {"python": "Python", "sql": "SQL", "algorithms": "Алгоритмы", "javascript": "JavaScript",
                "security": "Безопасность", "network": "Сети", "ml": "Машинное обучение",
                "embedded": "Встраиваемые системы", "concept": "Понимание",
                "testing": "Тестирование", "metrics": "Метрики", "pipelines": "Конвейеры данных",
                "requirements": "Требования"}


class StartIn(BaseModel):
    target_grade: Grade
    specialization: str | None = Field(None, description="По умолчанию — специализация из опроса")
    code_language: Literal["python", "javascript", "go", "java", "kotlin", "csharp"] = Field(
        "python", description="Язык, на котором показывать задания на чтение кода")
    vacancy_id: uuid.UUID | None = Field(
        None, description="Собрать темы теста из этой вакансии. Такой тест грейд не меняет: грейд даёт только "
                          "основной тест специализации")
    mode: Literal["grade", "express"] = "grade"


class VacancyExamIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field("", max_length=4000)
    skills: list[str] = Field(default_factory=list, max_length=30)
    role: str | None = None
    grade: Grade | None = None


class AnswerIn(BaseModel):
    item_token: str = Field(min_length=16, max_length=64)
    answer_index: int | None = Field(None, ge=0, le=9, description="Номер варианта, если у задания есть варианты")
    answer_text: str | None = Field(None, max_length=32, description="Число, если ответ вводится (answer_mode=number)")


class OptionOut(BaseModel):
    index: int
    text: str


class ItemOut(BaseModel):
    token: str
    seq: int
    stem: str
    code: str | None
    language: str | None
    answer_mode: Literal["choice", "number"] = Field(
        description="number: ответ — целое число, вводится без вариантов; choice: выбрать один из вариантов")
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
    wilson_low: float | None = None


class PersonFitOut(BaseModel):
    lz_star: float
    review: bool = Field(description="Ответы расходятся с моделью: повод пересдать, не вывод о списывании")


class ResultOut(BaseModel):
    # first_confirmation | upgrade | confirmed_again | kept_higher_grade | not_passed | vacancy_test
    outcome: str
    passed: bool
    upgraded: bool = Field(description="Грейд в профиле вырос: тест на уровень выше подтверждённого сдан")
    vacancy_test: bool = Field(False, description="Тест по вакансии: грейд не меняет")
    recommended_grade: str | None = Field(
        None, description="Уровень, на который стоит пройти отдельный основной тест; сам грейд не меняется")
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
    trial: bool = False
    note: str | None = None
    person_fit: PersonFitOut | None = None
    family_review: bool = False


class ProgressOut(BaseModel):
    answered: int
    min_items: int = cat.MIN_ITEMS
    max_items: int = cat.MAX_ITEMS
    p_pass: float | None = None
    theta: float | None = None
    se: float | None = None


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
        answer_mode="number" if it.typed else "choice",
        options=[] if it.typed else [OptionOut(index=i, text=t) for i, t in enumerate(it.options)], topic=it.topic,
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
    trial = (session.flags or {}).get("mode") == "express"
    passed = (not trial) and session.grade_assigned is not None and \
        GRADE_ORDER.index(session.grade_assigned) >= GRADE_ORDER.index(session.target_grade)
    flags = session.flags or {}
    outcome = reason or flags.get("outcome") or ("passed" if passed else "not_passed")
    raw_fit = flags.get("person_fit")
    fit = PersonFitOut(lz_star=float(raw_fit["lz_star"]), review=bool(raw_fit.get("review"))) \
        if isinstance(raw_fit, dict) and "lz_star" in raw_fit else None
    return ResultOut(
        outcome="trial" if trial else outcome, passed=passed, upgraded=outcome == "upgrade", trial=trial,
        vacancy_test=bool(flags.get("vacancy_id")), recommended_grade=flags.get("recommended_grade"),
        note="Пробный проход: грейд не подтверждается и в поиске не учитывается." if trial else None,
        earned_grade=None if trial else session.grade_assigned,
        confirmed_grade=None if trial else confirmed,
        p_pass=round(session.p_pass or 0.0, 3),
        p_upgrade=round(session.p_upgrade, 3) if session.p_upgrade is not None else None,
        theta=round(session.irt_theta or 0.0, 3), se=round(session.theta_se or 0.0, 3),
        items_count=session.items_count or len(answered), score=round(session.score or 0.0, 3),
        stop_reason=session.stop_reason, grade_locked_until=locked, person_fit=fit,
        family_review=bool(flags.get("family_cusum_review")),
        confirmed_skills=[SkillOut(name=n, share=round(v, 2)) for n, v in (skills or [])],
        topics=[TopicOut(topic=k, label=TOPIC_LABELS.get(k, k), answered=v[0], correct=v[1],
                         wilson_low=None if (low := wilson_lower(v[1], v[0])) is None else round(low, 3))
                for k, v in sorted(topics.items())],
        excluded_items=sum(1 for it in items if it.excluded),
    )


def _session_out(session: TestSession, items: list[TestSessionItem], result: ResultOut | None = None) -> SessionOut:
    current = items[-1] if items and items[-1].answered_at is None and session.status == "in_progress" else None
    answered = sum(1 for it in items if it.answered_at is not None)
    trial = (session.flags or {}).get("mode") == "express"
    return SessionOut(
        session_id=str(session.id), status=session.status, specialization=session.specialization,
        target_grade=session.target_grade, expires_at=session.expires_at.isoformat(),
        progress=ProgressOut(
            answered=answered,
            min_items=cat.EXPRESS_ITEMS if trial else cat.MIN_ITEMS,
            max_items=cat.EXPRESS_ITEMS if trial else cat.MAX_ITEMS,
            p_pass=round(session.p_pass, 3) if session.p_pass is not None else None,
            theta=round(session.irt_theta, 3) if session.irt_theta is not None else None,
            se=round(session.theta_se, 3) if session.theta_se is not None else None,
        ),
        item=_item_out(session.id, current) if current else None,
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
    if e.code == "answer_required":
        raise ApiError(422, "validation_error", "Нужен ответ: номер варианта или число") from e
    status_code = 410 if e.code == "session_expired" else 409
    raise ApiError(status_code, e.code) from e


@router.get("/blueprint")
async def blueprint():
    """Test structure per specialization: topics, shares and item families. Nothing here helps to cheat."""
    return {
        "min_items": cat.MIN_ITEMS, "max_items": cat.MAX_ITEMS, "pass_probability": cat.PASS_P,
        "express": settings.DEMO_MODE, "express_items": cat.EXPRESS_ITEMS,
        "express_minutes": cat.EXPRESS_MINUTES,
        "code_languages": LANGUAGE_LABELS,
        "next_test_probability": cat.RECOMMEND_NEXT_P, "concept_max_share": CONCEPT_MAX_SHARE,
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
                     db: AsyncSession = Depends(get_db),
                     idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    scope = f"assessment-start:{current['sub']}"
    digest = fingerprint(body.model_dump(mode="json"))
    try:
        stored = await idem_begin(scope, idempotency_key, digest)
    except IdempotencyConflict as e:
        raise ApiError(409, "conflict", e.message) from e
    except IdempotencyUnavailable as e:
        raise ApiError(503, "unavailable") from e
    if stored:
        return JSONResponse(stored["body"], status_code=stored["status"])
    try:
        out = await _start_test(body, current, db)
    except Exception:
        await idem_abort(scope, idempotency_key)
        raise
    await idem_finish(scope, idempotency_key, digest, 201, out.model_dump(mode="json"))
    return out


async def _start_test(body: StartIn, current: dict, db: AsyncSession) -> SessionOut:
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
    express = body.mode == "express"
    if express and not settings.DEMO_MODE:
        raise ApiError(404, "not_found", "Пробный тест включён только на демонстрационном стенде")
    if not express and await too_many(f"assessment_start:{participant_id}", limit=3, window_seconds=3600):
        raise ApiError(429, "rate_limited", "Не больше трёх попыток в час")
    if not express:
        locked = await check_cooldown(db, participant_id, spec)
        conf = await confirmation(db, participant_id, spec)
        if locked and conf and GRADE_ORDER.index(body.target_grade) > GRADE_ORDER.index(conf.grade):
            raise ApiError(429, "grade_locked", f"Повышение грейда доступно после {locked:%d.%m.%Y}",
                           details={"locked_until": locked.isoformat()})
        retake = await check_retake_interval(db, participant_id, body.target_grade, spec,
                                             vacancy_test=body.vacancy_id is not None)
        if retake:
            raise ApiError(429, "retake_cooldown", f"Пересдача на этот грейд доступна после {retake:%d.%m.%Y}",
                           details={"retake_at": retake.isoformat()})
    existing = await get_active_session(db, participant_id)
    if existing and existing.expires_at > datetime.now(UTC):
        raise ApiError(409, "conflict", "Уже есть незавершённый тест", details={"session_id": str(existing.id)})
    try:
        session, item = await start_session(
            db, participant_id, spec, body.target_grade, body.code_language, topic_shares, body.vacancy_id,
            mode="express" if express else "grade")
        await db.commit()
    except QuestionBankError as e:
        raise ApiError(503, "question_bank_empty") from e
    except IntegrityError as e:
        await db.rollback()
        raise ApiError(409, "conflict", "Уже есть незавершённый тест") from e
    return _session_out(session, [item])


@router.get("/active", response_model=SessionOut | None)
async def active(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    """The unfinished session, or null. «No test in progress» is the normal state, not an error."""
    session = await get_active_session(db, uuid.UUID(current["sub"]))
    if session is None or session.expires_at <= datetime.now(UTC):
        return None
    return _session_out(session, await session_items(db, session.id))


@router.get("/cooldown")
async def cooldown_status(specialization: str | None = None, current: dict = Depends(get_current_participant),
                          db: AsyncSession = Depends(get_db)):
    locked = await check_cooldown(db, uuid.UUID(current["sub"]), specialization)
    return {"locked": locked is not None, "locked_until": locked.isoformat() if locked else None}


class PracticeStartIn(BaseModel):
    vacancy_id: uuid.UUID | None = None
    topic: str | None = Field(None, max_length=40)


class PracticeAnswerIn(BaseModel):
    answer_index: int | None = Field(None, ge=0, le=9)
    answer_text: str | None = Field(None, max_length=32)


@router.get("/practice/weekly")
async def practice_weekly(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    """Task of the week from an employer's open vacancy (TZ 2.1, regular short tasks). null if none is open."""
    participant = await db.get(Participant, uuid.UUID(current["sub"]))
    if participant is None:
        raise ApiError(404, "not_found", "Профиль не найден")
    return await weekly_task(db, participant)


@router.post("/practice/start")
async def practice_start(body: PracticeStartIn, current: dict = Depends(get_current_participant),
                         db: AsyncSession = Depends(get_db)):
    participant = await db.get(Participant, uuid.UUID(current["sub"]))
    if participant is None:
        raise ApiError(404, "not_found", "Профиль не найден")
    open_rows = list(await db.scalars(select(PracticeAttempt).where(
        PracticeAttempt.participant_id == participant.id, PracticeAttempt.answered_at.is_(None))))
    reused = any(same_practice_request(row.topic, row.vacancy_id, body.topic, body.vacancy_id)
                 for row in open_rows)
    if not reused and await too_many(f"practice:{participant.id}", limit=12, window_seconds=3600):
        raise ApiError(429, "rate_limited", "Не больше двенадцати коротких заданий в час")
    try:
        row = await start_practice(db, participant, body.vacancy_id, body.topic)
        await db.commit()
    except LookupError as e:
        raise ApiError(404, "not_found", "Вакансия не найдена") from e
    return public_attempt(row)


@router.post("/practice/{attempt_id}/answer")
async def practice_answer(attempt_id: uuid.UUID, body: PracticeAnswerIn,
                          current: dict = Depends(get_current_participant),
                          db: AsyncSession = Depends(get_db)):
    participant = await db.get(Participant, uuid.UUID(current["sub"]))
    if participant is None:
        raise ApiError(404, "not_found", "Профиль не найден")
    try:
        result = await answer_practice(db, participant, attempt_id, body.answer_index, body.answer_text)
        await db.commit()
    except LookupError as e:
        raise ApiError(404, "not_found", "Задание не найдено") from e
    except ValueError as e:
        raise ApiError(422, "validation_error", "Нужен ответ: номер варианта или число") from e
    return result


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
        "vacancy_test": bool((s.flags or {}).get("vacancy_id")),
        "recommended_grade": (s.flags or {}).get("recommended_grade"),
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
                 db: AsyncSession = Depends(get_db),
                 idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    scope = f"assessment-answer:{current['sub']}"
    digest = fingerprint({"session_id": str(session_id), **body.model_dump(mode="json")})
    try:
        stored = await idem_begin(scope, idempotency_key, digest)
    except IdempotencyConflict as e:
        raise ApiError(409, "conflict", e.message) from e
    except IdempotencyUnavailable as e:
        raise ApiError(503, "unavailable") from e
    if stored:
        return JSONResponse(stored["body"], status_code=stored["status"])
    try:
        out = await _answer(session_id, body, current, db)
    except Exception:
        await idem_abort(scope, idempotency_key)
        raise
    try:
        await idem_finish(scope, idempotency_key, digest, 200, out.model_dump(mode="json"))
    except IdempotencyUnavailable as e:
        raise ApiError(503, "unavailable") from e
    return out


async def _answer(session_id: uuid.UUID, body: AnswerIn, current: dict, db: AsyncSession) -> SessionOut:
    try:
        session, nxt, fin = await answer_item(db, session_id, uuid.UUID(current["sub"]), body.item_token,
                                              body.answer_index, body.answer_text)
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
            "language": it.language, "answer_mode": "number" if it.typed else "choice",
            "options": [] if it.typed else it.options, "your_answer": it.answer_index, "your_text": it.answer_text,
            "correct": it.is_correct, "timed_out": it.timed_out, "excluded": it.excluded,
            "right_answer": None if static or it.typed else it.correct_index,
            "right_text": it.options[it.correct_index] if it.typed else None,
            "explanation": None if static else it.explanation,
        })
    return {"session_id": str(session.id), "items": out}
