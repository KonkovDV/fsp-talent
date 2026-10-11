import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_employer, get_current_participant
from app.api.errors import ApiError
from app.core.config import settings
from app.core.database import get_db
from app.models import (
    AccessLog,
    Application,
    CategoryAssignment,
    ConsentLog,
    DisciplineScore,
    Employer,
    Offer,
    Participant,
    Skill,
    Vacancy,
)
from app.models.participant import adult_confirmed
from app.services.categorization import DISCIPLINE_LABELS, GRADES, ROLES
from app.services.notify import Outbox, category_label, notify
from app.services.privacy import contacts_allowed
from app.services.scoring.engine import RANK_ORDER
from app.services.skills import normalize_skill
from app.services.trust_level import next_step, trust_level, vacancy_limit
from app.services.vacancies import match_vacancy, status_after_close
from app.services.vacancy_exam import form_exam
from app.services.vacancy_flags import vacancy_flags, vacancy_warnings

router = APIRouter(prefix="/vacancies", tags=["vacancies"])

_VACANCY_SCAN_LIMIT = 500
_PAGE_SIZE_MAX = 50


def _uuid(current: dict) -> uuid.UUID:
    return uuid.UUID(current["sub"])


class VacancyIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(None, max_length=4000)
    role: str | None = None
    grade: str | None = None
    grade_match: Literal["exact", "plus_minus", "any"] = "plus_minus"
    discipline: str | None = None
    min_rank: str | None = None
    # FIX (Pydantic v2): max_length on list must use Annotated
    skills: Annotated[list[str], Field(max_length=20)] = Field(default_factory=list)
    # TZ 2.2 п.1: the salary range is mandatory in a vacancy, as in an offer.
    salary_from_gross: int = Field(gt=0, le=100_000_000)
    salary_to_gross: int = Field(gt=0, le=100_000_000)
    work_format: Literal["remote", "office", "hybrid"] = "remote"
    allows_minors: bool = False

    @model_validator(mode="after")
    def _range(self):
        if self.role and self.role not in ROLES:
            raise ValueError("Неизвестная роль")
        if self.grade and self.grade not in GRADES:
            raise ValueError("Неизвестный грейд")
        if self.discipline and self.discipline not in DISCIPLINE_LABELS:
            raise ValueError("Неизвестная дисциплина")
        if self.min_rank and self.min_rank not in RANK_ORDER:
            raise ValueError("Неизвестный разряд")
        if self.salary_to_gross < self.salary_from_gross:
            raise ValueError("Верхняя граница зарплаты меньше нижней")
        floor = settings.MIN_MONTHLY_GROSS
        if self.salary_from_gross < floor or self.salary_to_gross < floor:
            raise ValueError(f"Вилка не ниже {floor} ₽ в месяц до вычета НДФЛ")
        return self


def _out(v: Vacancy, extra: dict | None = None) -> dict:
    card = {
        "id": str(v.id), "title": v.title, "description": v.description, "role": v.role, "grade": v.grade,
        "discipline": v.discipline, "min_rank": v.min_rank, "grade_match": v.grade_match or "plus_minus",
        "skills": v.skills or [],
        "salary_from": v.salary_from_gross, "salary_to": v.salary_to_gross,
        "work_format": v.work_format, "allows_minors": v.allows_minors, "is_open": v.is_open,
        "company": v.employer.company_name if v.employer else None,
        "flags": vacancy_flags(v.title, v.description),
        "warnings": vacancy_warnings(v.title, v.description),
    }
    if extra:
        card.update(extra)
    return card


@router.post("/", status_code=201)
async def create_vacancy(body: VacancyIn, current: dict = Depends(get_current_employer),
                         db: AsyncSession = Depends(get_db)):
    employer = await db.get(Employer, _uuid(current))
    if not employer:
        raise HTTPException(404, "Работодатель не найден")
    level = trust_level(employer)
    cap = vacancy_limit(level)
    opened = await db.scalar(select(func.count()).select_from(Vacancy).where(
        Vacancy.employer_id == employer.id, Vacancy.is_open.is_(True))) or 0
    if int(opened) >= cap:
        raise ApiError(429, "rate_limited",
                       f"На этом уровне доверия открытых вакансий не больше {cap}. {next_step(level)}")
    vacancy = Vacancy(
        employer_id=employer.id, title=body.title, description=(body.description or "").strip() or None,
        role=body.role, grade=body.grade, grade_match=body.grade_match,
        discipline=body.discipline, min_rank=body.min_rank, skills=_skills(body.skills),
        salary_from_gross=body.salary_from_gross, salary_to_gross=body.salary_to_gross,
        work_format=body.work_format, allows_minors=body.allows_minors,
    )
    db.add(vacancy)
    await db.flush()
    vacancy.employer = employer
    await db.commit()
    return _out(vacancy)


def _skills(raw_skills: list[str]) -> list[str]:
    skills = []
    for raw in raw_skills:
        name = normalize_skill(raw)
        if name and name not in skills:
            skills.append(name)
    return skills


@router.put("/{vacancy_id}")
async def update_vacancy(vacancy_id: uuid.UUID, body: VacancyIn,
                         current: dict = Depends(get_current_employer),
                         db: AsyncSession = Depends(get_db)):
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy or vacancy.employer_id != _uuid(current):
        raise HTTPException(404, "Вакансия не найдена")
    vacancy.title = body.title
    vacancy.description = (body.description or "").strip() or None
    vacancy.role = body.role
    vacancy.grade = body.grade
    vacancy.grade_match = body.grade_match
    vacancy.discipline = body.discipline
    vacancy.min_rank = body.min_rank
    vacancy.skills = _skills(body.skills)
    vacancy.salary_from_gross = body.salary_from_gross
    vacancy.salary_to_gross = body.salary_to_gross
    vacancy.work_format = body.work_format
    vacancy.allows_minors = body.allows_minors
    await db.commit()
    vacancy.employer = await db.get(Employer, vacancy.employer_id)
    return _out(vacancy)


@router.post("/exam")
async def preview_exam(body: VacancyIn, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    """Show the test this vacancy text would form. Answer keys stay on the server."""
    if not await db.get(Employer, _uuid(current)):
        raise HTTPException(404, "Работодатель не найден")
    exam = form_exam(body.title, body.description or "", list(body.skills), body.role, body.grade)
    exam.pop("topic_shares", None)
    return exam


@router.get("/mine")
async def my_vacancies(
    limit: int = Query(_PAGE_SIZE_MAX, ge=1, le=_PAGE_SIZE_MAX),
    offset: int = Query(0, ge=0),
    current: dict = Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(Vacancy)
        .where(Vacancy.employer_id == _uuid(current))
        .options(selectinload(Vacancy.employer))
        .order_by(Vacancy.created_at.desc())
        .limit(limit).offset(offset)
    )
    return [_out(v) for v in rows]


@router.post("/{vacancy_id}/close")
async def close_vacancy(vacancy_id: uuid.UUID, current: dict = Depends(get_current_employer),
                        db: AsyncSession = Depends(get_db)):
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy or vacancy.employer_id != _uuid(current):
        raise HTTPException(404, "Вакансия не найдена")
    vacancy.is_open = False
    apps = list(await db.scalars(select(Application).where(Application.vacancy_id == vacancy.id)))
    employer = await db.get(Employer, vacancy.employer_id)
    company = employer.company_name if employer else "Работодатель"
    outbox = Outbox()
    for application in apps:
        if status_after_close(application.status) is None:
            continue
        application.status = "closed"
        await notify(db, outbox, "participant", application.candidate_id, "application_status",
                     f"Отклик на «{vacancy.title}»: {STATUS_RU['closed']}",
                     f"{company} закрыла вакансию. Отклик больше не рассматривается.",
                     "/candidate/vacancies")
    await db.commit()
    await outbox.deliver()
    return {"is_open": False}


@router.get("/for-me")
async def vacancies_for_me(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    participant = await db.get(Participant, _uuid(current))
    if not participant:
        raise HTTPException(404, "Профиль не найден")
    category = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == participant.id))
    skills = list(await db.scalars(select(Skill.name).where(
        Skill.participant_id == participant.id, Skill.confirmed.is_(True))))
    scores = list(await db.scalars(select(DisciplineScore).where(DisciplineScore.participant_id == participant.id)))
    candidate = {
        "role": category.primary_role if category else None,
        "grade": category.grade if category else None,
        "skills": skills,
        "disciplines": [{"discipline": s.discipline, "best_rank": s.best_rank} for s in scores],
        "is_minor": not adult_confirmed(participant),
    }
    needs_guardian = participant.minor_now() and not participant.minor_consent_given
    applied = set(await db.scalars(
        select(Application.vacancy_id).where(Application.candidate_id == participant.id)))
    rows = list(await db.scalars(
        select(Vacancy).where(Vacancy.is_open.is_(True))
        .options(selectinload(Vacancy.employer))
        .order_by(Vacancy.created_at.desc())
        .limit(_VACANCY_SCAN_LIMIT)
    ))
    cards = []
    for vacancy in rows:
        hit = match_vacancy(candidate, {
            "role": vacancy.role, "grade": vacancy.grade, "grade_match": vacancy.grade_match,
            "discipline": vacancy.discipline,
            "min_rank": vacancy.min_rank, "skills": vacancy.skills or [],
            "allows_minors": vacancy.allows_minors, "is_open": vacancy.is_open,
        })
        if hit is None:
            continue
        cards.append(_out(vacancy, {**hit, "applied": vacancy.id in applied,
                                    "can_apply": not needs_guardian and not hit["needs_test"]}))
    if candidate["grade"]:
        cards.sort(key=lambda c: (-c["coverage"], c["title"]))
    # Without a grade the rows keep the query order: newest vacancy first.
    return cards


@router.get("/my-applications")
async def candidate_applications(current: dict = Depends(get_current_participant),
                                 db: AsyncSession = Depends(get_db)):
    """Statuses of the candidate's own applications. Other people's data is not included."""
    rows = list(await db.scalars(
        select(Application).where(Application.candidate_id == _uuid(current))
        .options(selectinload(Application.vacancy))
        .order_by(Application.created_at.desc())
        .limit(50)))
    return [{
        "id": str(a.id),
        "title": a.vacancy.title if a.vacancy else "",
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in rows]


@router.post("/{vacancy_id}/apply", status_code=201)
async def apply(vacancy_id: uuid.UUID, current: dict = Depends(get_current_participant),
                db: AsyncSession = Depends(get_db)):
    participant = await db.get(Participant, _uuid(current))
    vacancy = await db.get(Vacancy, vacancy_id)
    if not participant or not vacancy or not vacancy.is_open:
        raise HTTPException(404, "Вакансия не найдена")
    if participant.minor_now() and not participant.minor_consent_given:
        raise HTTPException(403, "Для отклика нужно согласие законного представителя")
    category = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == participant.id))
    skills = list(await db.scalars(select(Skill.name).where(
        Skill.participant_id == participant.id, Skill.confirmed.is_(True))))
    scores = list(await db.scalars(select(DisciplineScore).where(DisciplineScore.participant_id == participant.id)))
    hit = match_vacancy({
        "role": category.primary_role if category else None,
        "grade": category.grade if category else None,
        "skills": skills,
        "disciplines": [{"discipline": s.discipline, "best_rank": s.best_rank} for s in scores],
        "is_minor": not adult_confirmed(participant),
    }, {
        "role": vacancy.role, "grade": vacancy.grade, "grade_match": vacancy.grade_match,
        "discipline": vacancy.discipline,
        "min_rank": vacancy.min_rank, "skills": vacancy.skills or [],
        "allows_minors": vacancy.allows_minors, "is_open": True,
    })
    if hit is None:
        raise HTTPException(403, "Профиль не подходит под условия вакансии")
    if hit["needs_test"]:
        raise HTTPException(403, "Сначала подтвердите грейд тестом: вакансия ждёт определённый грейд")
    db.add(Application(vacancy_id=vacancy.id, candidate_id=participant.id, status="applied"))
    db.add(ConsentLog(participant_id=participant.id, event_type="vacancy_applied", actor_id=participant.id,
                      meta={"vacancy_id": str(vacancy.id)}))
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(409, "Отклик на эту вакансию уже есть") from e
    who = category_label(category.primary_role if category else None, category.grade if category else None)
    outbox = Outbox()
    await notify(db, outbox, "employer", vacancy.employer_id, "application_new",
                 f"Новый отклик на «{vacancy.title}»",
                 f"Откликнулся кандидат ({who}). "
                 "Контакты откликнувшегося доступны в разделе «Вакансии».",
                 "/employer/vacancies")
    from app.services.webhooks import deliver_due, enqueue
    await enqueue(db, vacancy.employer_id, "application.created", {
        "created_at": datetime.now(UTC).isoformat(), "employer_id": str(vacancy.employer_id),
        "vacancy": {"id": str(vacancy.id), "title": vacancy.title},
        "candidate": {"ref": str(participant.id), "name": participant.display_name, "email": participant.email,
                      "phone": participant.phone, "telegram": participant.telegram,
                      "category": {"specialization": category.primary_role if category else None,
                                   "grade": category.grade if category else None}},
    })
    await db.commit()
    await outbox.deliver()
    try:
        await deliver_due(db, vacancy.employer_id)
        await db.commit()
    except Exception:
        await db.rollback()
    return {"status": "applied"}


@router.get("/applications")
async def my_applications(
    limit: int = Query(_PAGE_SIZE_MAX, ge=1, le=_PAGE_SIZE_MAX),
    offset: int = Query(0, ge=0),
    current: dict = Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
):
    """List incoming applications, paginated."""
    rows = list(await db.scalars(
        select(Application).join(Vacancy).where(Vacancy.employer_id == _uuid(current))
        .options(selectinload(Application.vacancy))
        .order_by(Application.created_at.desc())
        .limit(limit).offset(offset)
    ))
    return [{
        "id": str(a.id), "vacancy_id": str(a.vacancy_id), "vacancy_title": a.vacancy.title,
        "candidate_id": str(a.candidate_id), "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "viewed_at": a.viewed_at.isoformat() if getattr(a, "viewed_at", None) else None,
    } for a in rows]


STATUS_RU = {"reviewing": "на рассмотрении", "invited": "приглашение на интервью", "rejected": "отказ",
             "closed": "вакансия закрыта"}


class ApplicationStatusUpdate(BaseModel):
    status: Literal["reviewing", "invited", "rejected", "closed"]


@router.patch("/applications/{application_id}/status")
async def update_application_status(
    application_id: uuid.UUID,
    body: ApplicationStatusUpdate,
    current: dict = Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
):
    """Change application status (employer side).

    Allowed transitions: applied -> reviewing -> invited | rejected | closed
    Guard: cannot overwrite candidate terminal states (accepted/rejected by candidate).
    """
    application = await db.get(Application, application_id, with_for_update=True)
    if not application:
        raise HTTPException(404, "Отклик не найден")
    vacancy = await db.get(Vacancy, application.vacancy_id)
    if not vacancy or vacancy.employer_id != _uuid(current):
        raise HTTPException(404, "Отклик не найден")
    if application.status in ("accepted", "rejected"):
        raise HTTPException(409, "Этот статус уже окончательный")
    changed = application.status != body.status
    application.status = body.status
    if application.viewed_at is None:
        application.viewed_at = datetime.now(UTC)
    outbox = Outbox()
    if changed:
        employer = await db.get(Employer, vacancy.employer_id)
        await notify(db, outbox, "participant", application.candidate_id, "application_status",
                     f"Отклик на «{vacancy.title}»: {STATUS_RU[body.status]}",
                     f"{employer.company_name if employer else 'Работодатель'} изменил статус вашего отклика: "
                     f"{STATUS_RU[body.status]}.", "/candidate/vacancies")
    await db.commit()
    await outbox.deliver()
    return {"id": str(application.id), "status": application.status}


@router.get("/applications/{application_id}/contacts")
async def application_contacts(application_id: uuid.UUID, current: dict = Depends(get_current_employer),
                               db: AsyncSession = Depends(get_db)):
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Отклик не найден")
    vacancy = await db.get(Vacancy, application.vacancy_id)
    if not vacancy or vacancy.employer_id != _uuid(current):
        raise HTTPException(404, "Отклик не найден")
    candidate = await db.get(Participant, application.candidate_id)
    if not candidate:
        raise HTTPException(404, "Кандидат не найден")
    if not await contacts_allowed(db, candidate):
        raise ApiError(403, "consent_withdrawn")
    # The candidate closed the contacts for this company on an accepted invitation: applications follow,
    # until a later invitation of the same company is accepted again.
    latest = await db.scalar(select(Offer).where(
        Offer.employer_id == vacancy.employer_id, Offer.candidate_id == candidate.id, Offer.status == "accepted")
        .order_by(Offer.created_at.desc()).limit(1))
    if latest is not None and latest.contacts_revoked_at is not None:
        raise ApiError(403, "contacts_revoked")
    db.add(AccessLog(employer_id=vacancy.employer_id, participant_id=candidate.id, access_type="application_contacts"))
    if getattr(application, "viewed_at", None) is None:
        try:
            application.viewed_at = datetime.now(UTC)
        except AttributeError:
            pass
    await db.commit()
    return {
        "candidate_id": str(candidate.id), "display_name": candidate.display_name,
        "email": candidate.email, "telegram": candidate.telegram, "phone": candidate.phone,
        "region": candidate.region,
    }
