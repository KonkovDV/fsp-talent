import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_participant
from app.api.errors import ApiError
from app.api.v1.messages import unread_counts
from app.core.config import settings
from app.core.database import get_db
from app.core.demo_guard import reject_protected
from app.core.ratelimit import too_many
from app.core.security import verify_password
from app.models import (
    AccessLog,
    Application,
    CandidateInterest,
    CandidateResume,
    CategoryAssignment,
    Complaint,
    ConsentLog,
    Employer,
    GradeConfirmation,
    Offer,
    Participant,
    Vacancy,
    VerifiableCredential,
)
from app.models.complaint import REASONS
from app.models.participant import Result, Skill
from app.models.profile import DisciplineScore
from app.services.account_close import close_allowed
from app.services.ai import providers
from app.services.ai.assistant import parse_resume
from app.services.assessment import calibration_open, calibration_until, sync_assessed_grade
from app.services.categorization import DISCIPLINE_LABELS, GRADES
from app.services.cities import CITIES
from app.services.employer_score import company_score
from app.services.fsp import identity as fsp_identity
from app.services.fsp.mock import STATUS_LABELS, get_fsp_adapter
from app.services.fsp.registry import FSPRegistryError
from app.services.growth import growth_gaps, next_grade, skill_reach
from app.services.guardian import consent_link, demo_consent_link, guardian_token
from app.services.identity import active_consent
from app.services.inn import published_inn
from app.services.mail import send_mail
from app.services.market import market_flag, quartiles, role_median, salary_band
from app.services.notify import Outbox, category_label, notify
from app.services.offers import expire_if_stale, expire_stale
from app.services.pdf_profile import MAX_PDF_BYTES, extract_pdf_text, profile_lines, render_profile_pdf
from app.services.privacy import erase_participant
from app.services.profile import ingest_from_fsp, rebuild_profile
from app.services.profile_completeness import profile_completeness
from app.services.reputation import for_employer as company_reputation
from app.services.search.cache import bump_bank_epoch
from app.services.search.pipeline import _bucket
from app.services.skills import (
    SkillDraft,
    normalize_skill,
    plan_skill_replacement,
    read_resume_evidence,
    skill_line,
    with_resume_token,
)
from app.services.survey import INDUSTRIES, SPECIALIZATIONS, WORK_GOALS
from app.services.trust import refresh_hold
from app.services.trust_level import LABELS
from app.services.trust_level import trust_level as company_trust
from app.services.vc.issuer import issue_derived_credential, issue_sd_jwt, present_sd_jwt

router = APIRouter(prefix="/candidates", tags=["candidates"])

PRIVACY_FIELDS = ("is_visible", "public_profile", "show_city", "show_stack", "show_fsp", "show_experience")
_PAGE_SIZE_MAX = 50


def _skill_view(s: Skill) -> dict:
    return {"name": s.name, "trust_level": s.trust_level, "source_quote": s.source_quote,
            "confirmed": s.confirmed,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "confirmed_at": s.confirmed_at.isoformat() if s.confirmed_at else None}


def discipline_score_view(ds) -> dict:
    return {
        "discipline": ds.discipline, "label": DISCIPLINE_LABELS.get(ds.discipline, ds.discipline),
        "score": ds.score, "sigma": ds.sigma, "lcb": ds.lcb, "confidence": ds.confidence,
        "best_rank": ds.best_rank,
        "rank_assigned_at": ds.rank_assigned_at.isoformat() if ds.rank_assigned_at else None,
        "rank_order_ref": ds.rank_order_ref, "events_count": ds.events_count,
    }


def _pid(current: dict) -> uuid.UUID:
    try:
        return uuid.UUID(current["sub"])
    except ValueError as e:
        raise HTTPException(401, "Invalid token subject") from e


def _log_privacy(db: AsyncSession, p: Participant, field: str, value: bool) -> None:
    db.add(ConsentLog(participant_id=p.id, event_type=f"{field}_{'on' if value else 'off'}",
                      actor_id=p.id, meta={"field": field, "value": value}))


@router.get("/me")
async def get_my_profile(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    p = await db.scalar(
        select(Participant).where(Participant.id == _pid(current)).options(
            selectinload(Participant.discipline_scores), selectinload(Participant.category),
            selectinload(Participant.results), selectinload(Participant.skills)))
    if not p or p.deleted_at is not None:
        raise HTTPException(404, "Профиль не найден")
    cat = p.category
    return {
        "id": str(p.id), "fsp_id": p.fsp_id, "has_fsp": p.fsp_id is not None,
        "fsp_linked_at": p.fsp_linked_at.isoformat() if p.fsp_linked_at else None,
        "display_name": p.display_name, "region": p.region,
        "birth_date": p.birth_date.isoformat() if p.birth_date else None,
        "email": p.email, "email_verified": p.email_verified_at is not None,
        "telegram": p.telegram, "phone": p.phone, "github": p.github,
        "experience_years": p.experience_years, "declared_grade": p.declared_grade,
        "specialization": p.specialization, "industry": p.industry, "work_goal": p.work_goal,
        "work_formats": list(p.work_formats or []),
        "survey_done": p.survey_at is not None,
        "calibration_until": calibration_until(p.category_opened_at).isoformat()
        if calibration_open(p.category_opened_at, datetime.now(UTC)) else None,
        "confirmations": [{"specialization": c.specialization, "grade": c.grade, "p_pass": c.p_pass,
                           "confirmed_at": c.confirmed_at.isoformat(),
                           "locked_until": c.locked_until.isoformat() if c.locked_until else None}
                          for c in await db.scalars(select(GradeConfirmation).where(
                              GradeConfirmation.participant_id == p.id))],
        "assessed_grade": p.assessed_grade,
        "certificate_grade": getattr(p, "certificate_grade", None),
        "assessed_at": p.assessed_at.isoformat() if p.assessed_at else None,
        "grade_locked_until": p.grade_locked_until.isoformat() if p.grade_locked_until else None,
        "is_visible": p.is_visible, "public_profile": p.public_profile, "show_city": p.show_city,
        "show_stack": p.show_stack, "show_fsp": p.show_fsp, "show_experience": p.show_experience,
        "soft_skills": list(p.soft_skills or []),
        "job_search": p.job_search,
        "is_minor": p.minor_now(), "minor_consent_given": p.minor_consent_given, "guardian_email": p.guardian_email,
        "guardian_demo_link": (
            demo_consent_link(p.id, p.guardian_email) if p.minor_now() and not p.minor_consent_given else None
        ),
        "profile_version": p.profile_version,
        "salary_from": p.salary_from_gross, "salary_to": p.salary_to_gross,
        "discoverable": p.discoverable,
        "primary_role": cat.primary_role if cat else None,
        "grade": cat.grade if cat else None,
        "grade_source": cat.grade_source if cat else None,
        "stack": cat.stack if cat else [],
        "explanation": cat.explanation if cat else [],
        "skills": [_skill_view(s) for s in p.skills],
        "discipline_scores": [discipline_score_view(ds) for ds in sorted(p.discipline_scores, key=lambda d: -d.lcb)],
        "results_count": len(p.results),
        "completeness": profile_completeness(
            email_verified=p.email_verified_at is not None,
            survey_done=p.survey_at is not None,
            declared_grade=p.declared_grade,
            assessed_grade=p.assessed_grade,
            skill_count=len(p.skills or []),
            salary_from=p.salary_from_gross,
            salary_to=p.salary_to_gross,
            region=p.region,
            work_formats=p.work_formats,
        ),
    }


@router.get("/me/career")
async def my_career(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    """One confirmed skill that would close the most open vacancies. The grade does not move."""
    from app.models import Employer
    from app.services.career_gap import career_gap
    from app.services.skills import extract_skills, normalize_skill

    pid = _pid(current)
    have = {name for name in await db.scalars(select(Skill.name).where(
        Skill.participant_id == pid, Skill.confirmed.is_(True)))}
    found = (await db.execute(
        select(Vacancy).join(Employer, Employer.id == Vacancy.employer_id).where(
            Vacancy.is_open.is_(True), Employer.suspended_at.is_(None), Employer.guest_until.is_(None))
        .limit(40)
    )).scalars().all()
    vacancies = []
    for vacancy in found:
        names = {n for raw in (vacancy.skills or []) if (n := normalize_skill(raw))}
        names |= {item.skill for item in extract_skills(f"{vacancy.title}\n{vacancy.description or ''}")}
        if names:
            vacancies.append(names)
    hint = career_gap(have, vacancies)
    return hint or {"skill": None, "gained": 0, "vacancies": len(vacancies)}


@router.get("/me/salary-market")
async def my_salary_market(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    """Quartiles of named wishes in the candidate's own category.

    Same five-person floor as the employer market: a thinner cell is omitted, and no single wish is returned.
    """
    p = await db.get(Participant, _pid(current))
    if not p or p.deleted_at is not None:
        raise HTTPException(404, "Профиль не найден")
    cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == p.id))
    role = cat.primary_role if cat else None
    grade = cat.grade if cat else None
    if not role or not grade:
        return {"role": role, "grade": grade, "cell": None, "band": None}
    amounts = list(await db.scalars(
        select(Participant.salary_from_gross)
        .join(CategoryAssignment, CategoryAssignment.participant_id == Participant.id)
        .where(CategoryAssignment.primary_role == role, CategoryAssignment.grade == grade,
               Participant.salary_from_gross.is_not(None), Participant.deleted_at.is_(None),
               Participant.is_visible.is_(True))))
    cell = quartiles([int(amount) for amount in amounts if amount])
    return {"role": role, "grade": grade, "cell": cell, "band": salary_band(p.salary_from_gross, cell)}


@router.get("/me/growth")
async def my_growth(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    """Skills named by the next grade of the same specialization and missing from this profile.

    A grade with fewer than five visible people is omitted, and so is a skill named by fewer than five.
    The list does not change the candidate's grade.
    """
    p = await db.get(Participant, _pid(current))
    if not p or p.deleted_at is not None:
        raise HTTPException(404, "Профиль не найден")
    cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == p.id))
    role = cat.primary_role if cat else None
    grade = cat.grade if cat else None
    nxt = next_grade(grade)
    if not role or not nxt:
        reach = await _open_need_reach(db, role, p.id) if role else []
        return {"role": role, "grade": grade, "next_grade": nxt, "people": None, "gaps": [],
                "next_market": None, "need_reach": reach}
    visible = (Participant.deleted_at.is_(None), Participant.is_visible.is_(True),
               CategoryAssignment.primary_role == role, CategoryAssignment.grade == nxt)
    people = await db.scalar(
        select(func.count())
        .select_from(Participant)
        .join(CategoryAssignment, CategoryAssignment.participant_id == Participant.id)
        .where(*visible))
    people = int(people or 0)
    rows = (await db.execute(
        select(Skill.name, func.count())
        .join(Participant, Participant.id == Skill.participant_id)
        .join(CategoryAssignment, CategoryAssignment.participant_id == Participant.id)
        .where(*visible)
        .group_by(Skill.name))).all()
    owned = {skill.name for skill in await db.scalars(select(Skill).where(Skill.participant_id == p.id))}
    amounts = list(await db.scalars(
        select(Participant.salary_from_gross)
        .join(CategoryAssignment, CategoryAssignment.participant_id == Participant.id)
        .where(*visible, Participant.salary_from_gross.is_not(None))))
    shown = people if people >= 5 else None
    from app.models import Need, NeedVersion
    versions = list(await db.scalars(
        select(NeedVersion.params)
        .join(Need, Need.id == NeedVersion.need_id)
        .where(Need.archived.is_(False), NeedVersion.version == Need.version)))
    pairs = [((params or {}).get("role"), list((params or {}).get("skills") or [])) for params in versions]
    return {
        "role": role, "grade": grade, "next_grade": nxt, "people": shown,
        "gaps": growth_gaps(role, owned, {name: int(n) for name, n in rows}, people),
        "next_market": quartiles([int(amount) for amount in amounts if amount]),
        "need_reach": skill_reach(role, owned, pairs),
    }


async def _open_need_reach(db: AsyncSession, role: str | None, participant_id: uuid.UUID) -> list[dict]:
    """Needs whose current version is one required skill away. Archived needs stay out."""
    if not role:
        return []
    from app.models import Need, NeedVersion
    owned = {skill.name for skill in await db.scalars(select(Skill).where(Skill.participant_id == participant_id))}
    versions = list(await db.scalars(
        select(NeedVersion.params)
        .join(Need, Need.id == NeedVersion.need_id)
        .where(Need.archived.is_(False), NeedVersion.version == Need.version)))
    needs = []
    for params in versions:
        params = params or {}
        needs.append((params.get("role"), list(params.get("skills") or [])))
    return skill_reach(role, owned, needs)


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    source_quote: str | None = Field(None, max_length=500)


class ProfileUpdate(BaseModel):
    """Self-service profile fields.

    minor_consent_given is deliberately absent: consent of a legal representative cannot be
    granted by the minor through the same account. It must come from a separate guardian flow.
    """
    experience_years: int | None = Field(None, ge=0, le=50)
    declared_grade: Literal["intern", "junior", "middle", "senior", "lead"] | None = None
    # FIX (Pydantic v2): max_length on list[T] must use Annotated[], not Field() kwarg.
    # Old: list[SkillIn] | None = Field(None, max_length=40) -- silently ignored the limit.
    skills: Annotated[list[SkillIn], Field(max_length=40)] | None = None
    # Proof that a resume quote was extracted here, not typed into the request.
    resume_tokens: Annotated[list[Annotated[str, Field(max_length=24000)]], Field(max_length=8)] = Field(
        default_factory=list)
    # The login email is not editable here: it is the confirmed contact an employer receives.
    display_name: str | None = Field(None, min_length=1, max_length=200)
    region: str | None = Field(None, max_length=100)
    telegram: str | None = Field(None, max_length=64)
    phone: str | None = Field(None, max_length=20)
    github: str | None = Field(None, max_length=40)
    public_profile: bool | None = None
    is_visible: bool | None = None
    show_city: bool | None = None
    show_stack: bool | None = None
    show_fsp: bool | None = None
    show_experience: bool | None = None
    soft_skills: list[str] | None = Field(None, max_length=5)
    job_search: Literal["active", "open", "not_looking"] | None = None
    salary_from_gross: int | None = Field(None, ge=0, le=100_000_000)
    salary_to_gross: int | None = Field(None, ge=0, le=100_000_000)
    birth_date: date | None = None
    expected_version: int | None = Field(None, ge=0)


@router.put("/me/profile")
async def update_profile(body: ProfileUpdate, current: dict = Depends(get_current_participant),
                         db: AsyncSession = Depends(get_db)):
    p = await db.get(Participant, _pid(current))
    if not p:
        raise HTTPException(404, "Профиль не найден")
    data = body.model_dump(exclude_unset=True)
    if body.expected_version is not None and body.expected_version != (p.profile_version or 0):
        raise ApiError(409, "conflict", "Профиль уже изменился. Обновите страницу.")
    if data.get("public_profile") and p.minor_now():
        raise HTTPException(403, "Именная страница недоступна для несовершеннолетних")
    if data.get("public_profile") and not p.public_profile and \
            await active_consent(db, "participant", p.id, "pd_distribution") is None:
        # 152-FZ art. 10.1: a public page needs a separate consent to distribution.
        raise ApiError(409, "consent_required", "Для публичной страницы нужно согласие на распространение данных",
                       details={"missing": ["pd_distribution"]})
    if "declared_grade" in data and data["declared_grade"] not in (*GRADES, None):
        raise HTTPException(400, "Неизвестный грейд")
    for field in ("experience_years", "declared_grade"):
        if field in data:
            setattr(p, field, data[field])
    if "soft_skills" in data and data["soft_skills"] is not None:
        from app.services.soft_skills import clean
        try:
            p.soft_skills = clean(data["soft_skills"])
        except ValueError as exc:
            raise ApiError(422, "validation_error", str(exc)) from exc
    city_changed = False
    for field in PRIVACY_FIELDS:
        value = data.get(field)
        if value is None:
            continue
        if value != getattr(p, field):
            _log_privacy(db, p, field, value)
            if field == "show_city":
                city_changed = True
        setattr(p, field, value)
    for field in ("telegram", "phone"):
        if field in data:
            setattr(p, field, data[field] or None)
    if "github" in data:
        from app.services.code_profile import clean_github
        try:
            p.github = clean_github(data["github"])
        except ValueError as exc:
            raise ApiError(422, "validation_error", str(exc)) from exc
    if data.get("display_name"):
        p.display_name = data["display_name"].strip()
    if "region" in data and p.fsp_id is None:
        # With FSP linked, the region comes from the protocols.
        p.region = (data["region"] or "").strip() or None
    if "job_search" in data and data["job_search"]:
        p.job_search = data["job_search"]
    if "birth_date" in data and data["birth_date"] is not None and p.fsp_id is None:
        born = data["birth_date"]
        if born > date.today():
            raise ApiError(422, "validation_error", "Дата рождения ещё не наступила")
        from app.services.profile import age_on
        if age_on(born, date.today()) < 15:
            raise ApiError(422, "too_young", "Регистрация открыта с 15 лет")
        if p.birth_date is not None and p.birth_date != born:
            # Stand audit S4: a minor could move the date and skip the guardian's consent. Once saved,
            # the date changes only through support, with the guardian when the person is a minor.
            raise ApiError(409, "birth_date_locked",
                           "Дата рождения уже сохранена. Исправить её можно только через поддержку.")
        p.birth_date = born
        p.is_minor = age_on(born, date.today()) < 18
    for field in ("salary_from_gross", "salary_to_gross"):
        if field in data:
            setattr(p, field, data[field])
    if p.salary_from_gross and p.salary_to_gross and p.salary_from_gross > p.salary_to_gross:
        raise ApiError(422, "validation_error", "Зарплата «от» больше, чем «до»")
    p.profile_version = (p.profile_version or 0) + 1
    if "skills" in data:
        existing = list(await db.scalars(select(Skill).where(Skill.participant_id == p.id)))
        incoming = []
        for item in data["skills"]:
            canonical = normalize_skill(item["name"])
            quote = (item.get("source_quote") or "").strip() or None
            incoming.append((canonical or "", item["name"][:200], quote))
        allowed: set[tuple[str, str]] = set()
        for token in data.get("resume_tokens") or []:
            allowed |= read_resume_evidence(token, str(p.id))
        drafts = plan_skill_replacement(
            [SkillDraft(s.name, s.raw_name, s.source_quote, s.trust_level, s.confirmed,
                        s.created_at, s.confirmed_at) for s in existing],
            incoming, datetime.now(UTC), allowed)
        await db.execute(delete(Skill).where(Skill.participant_id == p.id))
        await db.flush()
        db.add_all([
            Skill(participant_id=p.id, name=d.name, raw_name=d.raw_name, source_quote=d.source_quote,
                  trust_level=d.trust_level, confirmed=d.confirmed, created_at=d.created_at,
                  confirmed_at=d.confirmed_at)
            for d in drafts
        ])
    try:
        await db.flush()
    except IntegrityError as e:
        raise HTTPException(409, "Данные конфликтуют с другим профилем") from e
    await rebuild_profile(db, p)
    await db.commit()
    if city_changed:
        await bump_bank_epoch()
    return {"ok": True}


class VisibilityUpdate(BaseModel):
    is_visible: bool


@router.patch("/me/visibility")
async def update_visibility(body: VisibilityUpdate, current: dict = Depends(get_current_participant),
                            db: AsyncSession = Depends(get_db)):
    p = await db.get(Participant, _pid(current))
    if not p:
        raise HTTPException(404, "Профиль не найден")
    if body.is_visible != p.is_visible:
        _log_privacy(db, p, "is_visible", body.is_visible)
    p.is_visible = body.is_visible
    await db.commit()
    await bump_bank_epoch()
    return {"is_visible": p.is_visible, "discoverable": p.discoverable}


class DeleteAccountIn(BaseModel):
    confirm: str = Field(..., max_length=20)
    password: str = Field("", max_length=72)


@router.delete("/me")
async def delete_my_account(body: DeleteAccountIn, current: dict = Depends(get_current_participant),
                            db: AsyncSession = Depends(get_db)):
    """Erase the account now (152-FZ, art. 21): contacts, name, FSP link and skills are removed,
    pending invitations are withdrawn. Anonymous sport results and the consent log stay.
    The word stops a stray click. An account with a password also has to type it."""
    p = await db.get(Participant, _pid(current))
    if not p or p.deleted_at is not None:
        raise HTTPException(404, "Профиль не найден")
    has_password = bool(p.password_hash)
    password_ok = has_password and verify_password(body.password, p.password_hash)
    problem = close_allowed(body.confirm, has_password, password_ok)
    if problem == "word":
        raise ApiError(422, "delete_confirm")
    if problem == "password":
        raise ApiError(401, "invalid_credentials", "Пароль не подошёл")
    reject_protected(p.email)
    await erase_participant(db, p, reason="account_deleted")
    await db.commit()
    return {"deleted": True}


@router.get("/me/results")
async def get_my_results(
    limit: int = Query(50, ge=1, le=_PAGE_SIZE_MAX),
    offset: int = Query(0, ge=0),
    current: dict = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of FSP results for this participant."""
    rows = await db.scalars(
        select(Result)
        .where(Result.participant_id == _pid(current))
        .order_by(Result.event_date.desc())
        .limit(limit).offset(offset)
    )
    return [{
        "id": str(r.id), "event_name": r.event_name, "discipline": r.discipline,
        "discipline_label": DISCIPLINE_LABELS.get(r.discipline, r.discipline),
        "competition_status": r.competition_status,
        "status_label": STATUS_LABELS.get(r.competition_status, r.competition_status),
        "place": r.place, "total_participants": r.total_participants,
        "is_team": r.is_team, "team_size": r.team_size, "event_date": r.event_date.isoformat(),
        "protocol_url": r.protocol_url, "trust_level": r.trust_level,
        "ekp_number": (r.raw_data or {}).get("ekp_number"),
    } for r in rows]


@router.post("/me/certificate")
async def import_certificate(file: UploadFile = File(...), current: dict = Depends(get_current_participant),
                             db: AsyncSession = Depends(get_db)):
    """Skills quoted in a certificate. A confirmed test skill is left as it is. The grade does not move."""
    from app.services.certificate_evidence import certificate_skills
    from app.services.protocol_file import text_of_pdf

    if await too_many(f"certificate:{_pid(current)}", limit=10, window_seconds=3600):
        raise ApiError(429, "rate_limited", "Слишком много файлов. Подождите час.")
    person = await db.get(Participant, _pid(current))
    if person is None or person.deleted_at is not None:
        raise HTTPException(404, "Профиль не найден")
    grade_before = person.assessed_grade
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise ApiError(413, "payload_too_large", "Файл больше 2 МБ")
    try:
        if (file.filename or "").lower().endswith(".pdf"):
            text = text_of_pdf(raw)
        else:
            text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        raise ApiError(422, "validation_error", "Файл не читается") from exc
    found = certificate_skills(text)
    if found is None:
        raise ApiError(422, "validation_error",
                       "В файле нет свидетельства: нужно упоминание КИТ, i.moscow или компетенций")
    existing = {row.name: row for row in await db.scalars(select(Skill).where(Skill.participant_id == person.id))}
    kept = []
    now = datetime.now(UTC)
    for name, quote in found:
        row = existing.get(name)
        if row is not None and row.trust_level == "test_confirmed":
            continue
        if row is None:
            row = Skill(participant_id=person.id, name=name, raw_name=name, created_at=now)
            db.add(row)
            existing[name] = row
        row.source_quote = quote
        row.trust_level = "resume_confirmed"
        row.confirmed = True
        row.confirmed_at = now
        kept.append(name)
    await db.commit()
    return {"skills": kept, "grade_unchanged": person.assessed_grade == grade_before}


@router.post("/me/protocols")
async def import_protocols(file: UploadFile = File(...), current: dict = Depends(get_current_participant),
                           db: AsyncSession = Depends(get_db)):
    """A protocol file when the registry is silent. The grade and the match score stay put."""
    from app.services.profile import rebuild_profile
    from app.services.protocol_file import certificate_grade, parse_protocol_text, text_of_pdf, text_of_xlsx

    if await too_many(f"protocols:{_pid(current)}", limit=10, window_seconds=3600):
        raise ApiError(429, "rate_limited", "Слишком много файлов. Подождите час.")
    person = await db.get(Participant, _pid(current))
    if person is None or person.deleted_at is not None:
        raise HTTPException(404, "Профиль не найден")
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise ApiError(413, "payload_too_large", "Файл больше 2 МБ")
    name = (file.filename or "").lower()
    try:
        if name.endswith(".pdf"):
            text = text_of_pdf(raw)
        elif name.endswith(".xlsx"):
            text = text_of_xlsx(raw)
        else:
            text = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        raise ApiError(422, "validation_error", "Файл не читается") from exc
    parsed = parse_protocol_text(text)
    named = certificate_grade(text)
    if named:
        person.certificate_grade = named
    if not parsed and not named:
        raise ApiError(422, "validation_error", "В файле нет строк протокола: дисциплина, дата, место, всего")
    known = set(await db.scalars(select(Result.event_id).where(Result.participant_id == person.id)))
    added = 0
    for row in parsed:
        if row.event_id in known:
            continue
        db.add(Result(
            participant_id=person.id, event_id=row.event_id, event_name=row.event_name,
            discipline=row.discipline, competition_status=row.competition_status,
            place=row.place, total_participants=row.total_participants, is_team=False, team_size=1,
            role="participant", event_date=row.event_date, trust_level="file_import",
            raw_data={"source": "file"},
        ))
        added += 1
    if added:
        await rebuild_profile(db, person)
    await db.commit()
    return {"added": added, "read": len(parsed),
            "certificate_grade": getattr(person, "certificate_grade", None), "grade_unchanged": True}


@router.post("/me/results/{result_id}/presentation")
async def present_result(result_id: uuid.UUID, current: dict = Depends(get_current_participant),
                         db: AsyncSession = Depends(get_db)):
    """A signed card with the year, the status and the place band. The event title is not included."""
    pid = _pid(current)
    if await too_many(f"presentation:{pid}", limit=30):
        raise ApiError(429, "rate_limited", "Слишком много запросов краткого удостоверения")
    result = await db.get(Result, result_id)
    if result is None or result.participant_id != pid:
        raise HTTPException(404, "Результат не найден")
    year = result.event_date.year
    status = STATUS_LABELS.get(result.competition_status, result.competition_status)
    bucket = _bucket(result.place, result.total_participants)
    discipline = DISCIPLINE_LABELS.get(result.discipline, result.discipline)
    credential = issue_derived_credential(
        str(uuid.uuid4()), str(pid),
        year=year, status=status, bucket=bucket, discipline=discipline,
    )
    token, disclosures = issue_sd_jwt(str(pid), {
        "year": year, "competitionStatus": status, "bucket": bucket, "discipline": discipline,
        "eventName": result.event_name,
    })
    shown = present_sd_jwt(token, disclosures, {"year", "competitionStatus", "bucket", "discipline"})
    db.add(ConsentLog(participant_id=pid, event_type="derived_claim_issued", actor_id=pid,
                      meta={"result_id": str(result.id), "fields": ["year", "status", "bucket", "discipline"]}))
    await db.commit()
    return {"credential": credential, "sd_jwt": shown}


@router.post("/me/credentials/{credential_id}/revoke")
async def revoke_credential(credential_id: uuid.UUID, current: dict = Depends(get_current_participant),
                            db: AsyncSession = Depends(get_db)):
    """The signature stays verifiable. The status document starts saying the credential is revoked."""
    pid = _pid(current)
    vc = await db.get(VerifiableCredential, credential_id)
    if vc is None or vc.participant_id != pid:
        raise HTTPException(404, "Удостоверение не найдено")
    if vc.revoked_at is None:
        vc.revoked_at = datetime.now(UTC)
        db.add(ConsentLog(participant_id=pid, event_type="credential_revoked", actor_id=pid,
                          meta={"credential_id": str(vc.id)}))
        await db.commit()
    return {"revoked_at": vc.revoked_at.isoformat()}


@router.get("/me/offers")
async def get_my_offers(
    limit: int = Query(_PAGE_SIZE_MAX, ge=1, le=_PAGE_SIZE_MAX),
    offset: int = Query(0, ge=0),
    current: dict = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    """Offers sent to this candidate. A waiting one stays on the first page, ahead of newer closed ones."""
    rows = list(await db.scalars(
        select(Offer)
        .where(Offer.candidate_id == _pid(current))
        .options(selectinload(Offer.employer))
        .order_by(case((Offer.status == "pending", 0), else_=1), Offer.created_at.desc())
        .limit(limit).offset(offset)
    ))
    changed = expire_stale(rows)
    now = datetime.now(UTC)
    for o in rows:
        # TZ 2.2 п.3: the employer sees that the invitation was viewed.
        if o.status == "pending" and o.candidate_viewed_at is None:
            o.candidate_viewed_at = now
            changed = True
    if changed:
        await db.commit()
    unread = await unread_counts(db, [o.id for o in rows if o.status == "accepted"], "participant")
    cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == _pid(current)))
    median = await role_median(db, cat.primary_role if cat else None, cat.grade if cat else None)
    reputations = {}
    for offer in rows:
        if offer.employer_id not in reputations:
            reputations[offer.employer_id] = await company_reputation(db, offer.employer)
    marked = set(await db.scalars(select(CandidateInterest.employer_id).where(
        CandidateInterest.participant_id == _pid(current))))
    return [{
        "id": str(o.id), "company": o.employer.company_name, "company_id": str(o.employer_id), "role": o.role,
        # The company card the employer keeps (TZ: the candidate sees who invites). No personal data here.
        "company_profile": {"industry": o.employer.industry, "website": o.employer.website,
                            "about": o.employer.description, "inn_given": published_inn(o.employer.inn),
                            "rating": company_score(o.employer.company_name),
                            "trust_level": company_trust(o.employer),
                            "trust_label": LABELS[company_trust(o.employer)],
                            "reputation": reputations[o.employer_id]},
        "contact_method": o.contact_method,
        "salary_from": o.salary_from_gross, "salary_to": o.salary_to_gross,
        "market_flag": market_flag(o.salary_from_gross, o.salary_to_gross, median),
        "currency": o.currency, "work_format": o.work_format, "message": o.message,
        "perks": list(o.perks or []),
        "practice_stage": o.practice_stage,
        "company_interest": o.employer_id in marked,
        "status": o.status, "created_at": o.created_at.isoformat(),
        "expires_at": o.expires_at.isoformat() if o.expires_at else None,
        "contacts_revoked_at": o.contacts_revoked_at.isoformat() if o.contacts_revoked_at else None,
        "unread_messages": unread.get(o.id, 0),
    } for o in rows]


@router.post("/me/interests/{employer_id}", status_code=201)
async def mark_company_interest(employer_id: uuid.UUID, current: dict = Depends(get_current_participant),
                                db: AsyncSession = Depends(get_db)):
    """The specialist marks a company. The row stores two ids and no name."""
    employer = await db.get(Employer, employer_id)
    if employer is None or employer.suspended_at is not None:
        raise ApiError(404, "not_found", "Компания не найдена")
    pid = _pid(current)
    existing = await db.scalar(select(CandidateInterest.id).where(
        CandidateInterest.participant_id == pid, CandidateInterest.employer_id == employer_id))
    if existing is None:
        db.add(CandidateInterest(participant_id=pid, employer_id=employer_id, created_at=datetime.now(UTC)))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    return {"employer_id": str(employer_id), "interest": True}


@router.delete("/me/interests/{employer_id}")
async def clear_company_interest(employer_id: uuid.UUID, current: dict = Depends(get_current_participant),
                                 db: AsyncSession = Depends(get_db)):
    await db.execute(delete(CandidateInterest).where(
        CandidateInterest.participant_id == _pid(current), CandidateInterest.employer_id == employer_id))
    await db.commit()
    return {"employer_id": str(employer_id), "interest": False}


class ComplaintIn(BaseModel):
    reason: Literal["не_вакансия", "сбор_данных", "зарплата_не_та", "оскорбление", "другое"]
    offer_id: uuid.UUID | None = None
    vacancy_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one_object(self):
        if (self.offer_id is None) == (self.vacancy_id is None):
            raise ValueError("Укажите приглашение или вакансию")
        return self


@router.post("/me/complaints", status_code=201)
async def file_complaint(body: ComplaintIn, current: dict = Depends(get_current_participant),
                         db: AsyncSession = Depends(get_db)):
    """One complaint per candidate per invitation or vacancy. May pause that company's invitations."""
    if body.reason not in REASONS:
        raise ApiError(422, "validation_error", "Неизвестная причина жалобы")
    participant_id = _pid(current)
    employer_id: uuid.UUID | None = None
    if body.offer_id is not None:
        offer = await db.get(Offer, body.offer_id)
        if offer is None or offer.candidate_id != participant_id:
            raise ApiError(404, "not_found", "Приглашение не найдено")
        employer_id = offer.employer_id
    else:
        vacancy = await db.get(Vacancy, body.vacancy_id)
        if vacancy is None or not vacancy.is_open:
            raise ApiError(404, "not_found", "Вакансия не найдена")
        applied = await db.scalar(select(Application.id).where(
            Application.vacancy_id == vacancy.id, Application.candidate_id == participant_id))
        if applied is None:
            raise ApiError(404, "not_found", "Вакансия не найдена")
        employer_id = vacancy.employer_id
    row = Complaint(participant_id=participant_id, offer_id=body.offer_id, vacancy_id=body.vacancy_id,
                    reason=body.reason)
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "complaint_duplicate", "Жалоба на это приглашение или вакансию уже отправлена") from exc
    paused = await refresh_hold(db, employer_id)
    await db.commit()
    return {"id": str(row.id), "paused": paused}


class RespondIn(BaseModel):
    action: Literal["accept", "reject"]
    reason: Literal["salary", "format", "stack", "not_looking", "other"] | None = None


@router.post("/me/offers/{offer_id}/respond")
async def respond_to_offer(offer_id: uuid.UUID, body: RespondIn, current: dict = Depends(get_current_participant),
                           db: AsyncSession = Depends(get_db)):
    offer = await db.get(Offer, offer_id, with_for_update=True)
    if not offer or offer.candidate_id != _pid(current):
        raise HTTPException(404, "Оффер не найден")
    if offer.status != "pending":
        raise HTTPException(409, "Оффер уже обработан")
    if expire_if_stale(offer):
        await db.commit()
        raise HTTPException(409, "Срок оффера истёк")
    if body.action == "accept":
        offer.status = "accepted"
        offer.contacts_revealed_at = offer.responded_at = datetime.now(UTC)
        db.add(ConsentLog(participant_id=offer.candidate_id, event_type="contacts_revealed",
                          actor_id=offer.candidate_id, meta={"offer_id": str(offer.id)}))
    else:
        if body.reason is None:
            raise HTTPException(422, "Укажите причину отказа")
        offer.status = "rejected"
        offer.decline_reason = body.reason
        offer.responded_at = datetime.now(UTC)
        db.add(ConsentLog(participant_id=offer.candidate_id, event_type="offer_rejected",
                          actor_id=offer.candidate_id,
                          meta={"offer_id": str(offer.id), "reason": body.reason}))
    cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == offer.candidate_id))
    who = category_label(cat.primary_role if cat else None, cat.grade if cat else None)
    outbox = Outbox()
    if offer.status == "accepted":
        await notify(db, outbox, "employer", offer.employer_id, "offer_accepted",
                     f"Кандидат принял приглашение «{offer.role}»",
                     f"Кандидат ({who}) принял приглашение. Контакты открыты в разделе «Приглашения».",
                     "/employer/offers")
    else:
        await notify(db, outbox, "employer", offer.employer_id, "offer_rejected",
                     f"Кандидат отклонил приглашение «{offer.role}»",
                     f"Кандидат ({who}) отклонил приглашение. Подборка по потребности обновляется сама.",
                     "/employer/offers")
    person = await db.get(Participant, offer.candidate_id)
    event = {
        "created_at": datetime.now(UTC).isoformat(), "employer_id": str(offer.employer_id),
        "offer": {"id": str(offer.id), "role": offer.role, "salary_from": offer.salary_from_gross,
                  "salary_to": offer.salary_to_gross, "work_format": offer.work_format},
        "candidate": {"ref": str(offer.candidate_id),
                      "category": {"specialization": cat.primary_role if cat else None,
                                   "grade": cat.grade if cat else None,
                                   "grade_source": cat.grade_source if cat else None}},
    }
    if offer.status == "accepted" and person is not None:
        event["candidate"].update(name=person.display_name, email=person.email,
                                  phone=person.phone, telegram=person.telegram)
        event_type = "offer.accepted"
    else:
        event["reason"] = offer.decline_reason
        event_type = "offer.declined"
    from app.services.webhooks import deliver_due, enqueue
    await enqueue(db, offer.employer_id, event_type, event)
    await db.commit()
    from app.services.search.cache import publish_invite
    await publish_invite()
    await outbox.deliver()
    try:
        await deliver_due(db, offer.employer_id)
        await db.commit()
    except Exception:
        await db.rollback()
    suggest_hide = False
    if offer.status == "accepted":
        person = await db.get(Participant, offer.candidate_id)
        suggest_hide = person is not None and person.job_search != "not_looking"
    return {"status": offer.status, "suggest_hide": suggest_hide}


@router.post("/me/offers/{offer_id}/revoke-contacts")
async def revoke_contacts(offer_id: uuid.UUID, current: dict = Depends(get_current_participant),
                          db: AsyncSession = Depends(get_db)):
    """Close the contacts for one company after accepting its invitation. Other companies keep access.

    It closes every accepted invitation of that company and its access through vacancy applications.
    The global consent withdrawal (DELETE /me/consents/pd_candidate) stays for closing everything at once.
    """
    pid = _pid(current)
    offer = await db.get(Offer, offer_id, with_for_update=True)
    if not offer or offer.candidate_id != pid:
        raise HTTPException(404, "Оффер не найден")
    if offer.status != "accepted":
        raise ApiError(409, "conflict", "Закрыть контакты можно только по принятому приглашению")
    if offer.contacts_revoked_at is not None:
        return {"status": offer.status, "contacts_revoked_at": offer.contacts_revoked_at.isoformat()}
    now = datetime.now(UTC)
    same_company = list(await db.scalars(select(Offer).where(
        Offer.employer_id == offer.employer_id, Offer.candidate_id == pid, Offer.status == "accepted",
        Offer.contacts_revoked_at.is_(None))))
    for row in same_company:
        row.contacts_revoked_at = now
    db.add(ConsentLog(participant_id=pid, event_type="contacts_revoked", actor_id=pid,
                      meta={"offer_id": str(offer.id), "employer_id": str(offer.employer_id),
                            "offers": [str(o.id) for o in same_company]}))
    db.add(AccessLog(employer_id=offer.employer_id, participant_id=pid, access_type="contacts_revoked"))
    cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == pid))
    who = category_label(cat.primary_role if cat else None, cat.grade if cat else None)
    outbox = Outbox()
    await notify(db, outbox, "employer", offer.employer_id, "offer_contacts_revoked",
                 f"Кандидат закрыл контакты по приглашению «{offer.role}»",
                 f"Кандидат ({who}) закрыл для вашей компании свои контакты. Если вы их сохранили, "
                 "не используйте их для связи без нового согласия.", "/employer/offers")
    from app.services.webhooks import deliver_due, enqueue
    await enqueue(db, offer.employer_id, "contacts.revoked", {
        "created_at": now.isoformat(), "employer_id": str(offer.employer_id),
        "candidate": {"ref": str(pid), "delete": True},
    })
    await db.commit()
    await outbox.deliver()
    try:
        await deliver_due(db, offer.employer_id)
        await db.commit()
    except Exception:
        await db.rollback()
    return {"status": offer.status, "contacts_revoked_at": now.isoformat()}


class FspCallbackIn(BaseModel):
    code: str = Field(min_length=8, max_length=2048)
    state: str = Field(min_length=8, max_length=200)


@router.post("/me/fsp/authorize")
async def fsp_authorize(current: dict = Depends(get_current_participant)):
    """Start linking an FSP ID: the address of the provider's login page (OIDC code flow with PKCE).

    The FSP password is typed only on the provider's page, never on this site. In the demo the provider
    is a marked page of this site (FSP2000–FSP2099, password test); in production a Keycloak realm.
    """
    pid = _pid(current)
    if await too_many(f"fsp-link:{pid}", limit=10):
        raise ApiError(429, "rate_limited")
    started = await fsp_identity.start(pid)
    return {"authorize_url": started.authorize_url, "provider": fsp_identity.get_fsp_id_provider().name}


@router.post("/me/fsp/callback")
async def fsp_callback(body: FspCallbackIn, current: dict = Depends(get_current_participant),
                       db: AsyncSession = Depends(get_db)):
    """Finish linking: exchange the code, read the FSP ID from the verified ID token, load the protocols."""
    try:
        fsp_id = await fsp_identity.finish(_pid(current), body.code, body.state)
    except fsp_identity.FspIdError as e:
        raise ApiError(400, "fsp_invalid", "Вход через ФСП ID не подтверждён, начните привязку заново") from e
    p = await db.get(Participant, _pid(current), with_for_update=True)
    if not p:
        raise HTTPException(404, "Профиль не найден")
    if p.fsp_id is not None:
        raise ApiError(409, "fsp_already_linked")
    if await db.scalar(select(Participant.id).where(Participant.fsp_id == fsp_id)):
        raise ApiError(409, "fsp_taken")
    try:
        data = await get_fsp_adapter().fetch_participant(fsp_id)
    except FSPRegistryError as e:
        raise ApiError(503, "unavailable", "Реестр ФСП сейчас не отвечает, попробуйте позже") from e
    if data is None:
        raise ApiError(404, "fsp_not_found")
    await ingest_from_fsp(db, data, participant=p)
    await rebuild_profile(db, p)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ApiError(409, "fsp_taken") from e
    results = await db.scalar(select(func.count()).select_from(Result).where(Result.participant_id == p.id))
    return {"fsp_id": p.fsp_id, "results": results, "minor": p.minor_now()}


@router.post("/me/resume")
async def upload_resume(file: UploadFile = File(...), current: dict = Depends(get_current_participant)):
    """Read a PDF resume. The file is not stored; only the extracted text is parsed."""
    _pid(current)
    data = await file.read(MAX_PDF_BYTES + 1)
    try:
        text = extract_pdf_text(data)
    except ValueError as e:
        raise ApiError(422, "validation_error", "Нужен обычный PDF не больше 5 МБ") from e
    if not text:
        raise ApiError(422, "validation_error", "В PDF не нашлось текста")
    await providers.refresh()
    parsed = await parse_resume(text)
    return {"text": text[:4000], **with_resume_token(str(_pid(current)), parsed)}


async def _profile_pdf(db: AsyncSession, participant: Participant, named: bool) -> bytes:
    category = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == participant.id))
    skills = [skill_line(s.name, s.trust_level) for s in await db.scalars(
        select(Skill).where(Skill.participant_id == participant.id))]
    scores = list(await db.scalars(select(DisciplineScore).where(DisciplineScore.participant_id == participant.id)))
    lines = profile_lines(
        participant.display_name if named else None,
        SPECIALIZATIONS.get(category.primary_role, category.primary_role) if category else None,
        category.grade if category else participant.assessed_grade,
        skills,
        [{"label": DISCIPLINE_LABELS.get(s.discipline, s.discipline), "lcb": s.lcb, "rank": s.best_rank,
          "rank_assigned_at": s.rank_assigned_at.isoformat() if s.rank_assigned_at else None,
          "rank_order_ref": s.rank_order_ref}
         for s in scores],
    )
    return render_profile_pdf(lines)


@router.get("/me/profile.pdf")
async def my_profile_pdf(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    participant = await db.get(Participant, _pid(current))
    if participant is None:
        raise HTTPException(404, "Профиль не найден")
    pdf = await _profile_pdf(db, participant, named=True)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=profile.pdf",
                             "Cache-Control": "private, no-store"})


class GuardianIn(BaseModel):
    # The representative's address, never the candidate's login.
    guardian_email: Annotated[EmailStr, Field(max_length=200)]


@router.post("/me/guardian")
async def ask_guardian(body: GuardianIn, current: dict = Depends(get_current_participant),
                       db: AsyncSession = Depends(get_db)):
    """A candidate aged 15 to 17 sends the consent request to a legal representative (152-FZ art. 9 part 6)."""
    p = await db.get(Participant, _pid(current), with_for_update=True)
    if not p:
        raise HTTPException(404, "Профиль не найден")
    if not p.minor_now() or p.minor_consent_given:
        raise ApiError(409, "conflict", "Согласие представителя не требуется")
    email = str(body.guardian_email).strip().lower()
    if email == (p.email or "").lower():
        raise ApiError(422, "validation_error", "Укажите адрес родителя или другого законного представителя")
    if await too_many(f"guardian:{p.id}", limit=3, window_seconds=86_400):
        raise ApiError(429, "rate_limited", "Не больше трёх писем представителю в сутки")
    p.guardian_email = email
    db.add(ConsentLog(participant_id=p.id, event_type="guardian_requested", actor_id=p.id, meta={}))
    await db.commit()
    token = guardian_token(p.id, email)
    link = consent_link(settings.PUBLIC_BASE_URL, token)
    shown = demo_consent_link(p.id, email)
    await send_mail(email, "Согласие законного представителя — ФСП Талант",
                    f"{p.display_name or 'Ваш ребёнок'} зарегистрировался на платформе подбора ФСП Талант.\n"
                    "Работодатели увидят анонимную карточку кандидата только после вашего согласия на обработку "
                    "его персональных данных. Текст согласия и кнопка подтверждения — по ссылке:\n"
                    f"{link}\n\nЕсли вы не знаете, о ком речь, просто не открывайте ссылку.",
                    {"purpose": "guardian", "token": token})
    return {"ok": True, "guardian_email": email, "demo_link": shown}


class ExclusionIn(BaseModel):
    industries: list[str] = Field(default_factory=list, max_length=12)


class BlockIn(BaseModel):
    offer_id: uuid.UUID


@router.get("/me/exclusions")
async def my_exclusions(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    from app.models import CandidateBlock, Employer
    person = await db.get(Participant, _pid(current))
    if person is None:
        raise HTTPException(404, "Профиль не найден")
    rows = (await db.execute(
        select(CandidateBlock.employer_id, Employer.company_name)
        .join(Employer, Employer.id == CandidateBlock.employer_id)
        .where(CandidateBlock.participant_id == person.id))).all()
    return {"industries": list(person.excluded_industries or []),
            "companies": [{"id": str(eid), "name": name} for eid, name in rows]}


@router.put("/me/exclusions")
async def set_exclusions(body: ExclusionIn, current: dict = Depends(get_current_participant),
                         db: AsyncSession = Depends(get_db)):
    unknown = [code for code in body.industries if code not in INDUSTRIES or code == "any"]
    if unknown:
        raise ApiError(422, "validation_error", "Неизвестная предметная область")
    person = await db.get(Participant, _pid(current))
    if person is None:
        raise HTTPException(404, "Профиль не найден")
    person.excluded_industries = sorted(set(body.industries))
    await db.commit()
    return {"industries": person.excluded_industries}


@router.post("/me/blocks", status_code=201)
async def block_company(body: BlockIn, current: dict = Depends(get_current_participant),
                        db: AsyncSession = Depends(get_db)):
    """Hide this person from one company. Only a company that already wrote to them."""
    from app.models import CandidateBlock
    person_id = _pid(current)
    offer = await db.get(Offer, body.offer_id)
    if offer is None or offer.candidate_id != person_id:
        raise ApiError(404, "not_found", "Приглашение не найдено")
    row = await db.scalar(select(CandidateBlock).where(
        CandidateBlock.participant_id == person_id, CandidateBlock.employer_id == offer.employer_id))
    if row is None:
        db.add(CandidateBlock(participant_id=person_id, employer_id=offer.employer_id))
        await db.commit()
    return {"employer_id": str(offer.employer_id), "blocked": True}


@router.delete("/me/blocks/{employer_id}")
async def unblock_company(employer_id: uuid.UUID, current: dict = Depends(get_current_participant),
                          db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete as sql_delete

    from app.models import CandidateBlock
    await db.execute(sql_delete(CandidateBlock).where(
        CandidateBlock.participant_id == _pid(current), CandidateBlock.employer_id == employer_id))
    await db.commit()
    return {"employer_id": str(employer_id), "blocked": False}


@router.get("/survey-options")
async def survey_options():
    """Choices for the survey; public, so the registration flow can show them before login."""
    return {"specializations": SPECIALIZATIONS, "industries": INDUSTRIES, "work_goals": WORK_GOALS,
            "grades": list(GRADES), "cities": list(CITIES),
            "work_formats": {"office": "Офис", "hybrid": "Гибрид", "remote": "Удалённо"}}


class SurveyIn(BaseModel):
    specialization: str
    # The subject area (fintech, retail…) is optional: the IT direction is the specialization itself.
    industry: str = "any"
    work_goal: str = "job"
    # Q&A: the candidate chooses the grade; the first test checks exactly this choice.
    declared_grade: Literal["intern", "junior", "middle", "senior", "lead"]
    experience_years: int | None = Field(None, ge=0, le=50)
    salary_from_gross: int | None = Field(None, ge=0, le=100_000_000)
    salary_to_gross: int | None = Field(None, ge=0, le=100_000_000)
    # "net": the two amounts are take-home and get converted to gross before they are stored.
    salary_basis: Literal["gross", "net"] = "gross"
    work_formats: list[Literal["office", "hybrid", "remote"]] = Field(default_factory=list, max_length=3)
    region: str | None = Field(None, max_length=40)


@router.put("/me/survey")
async def save_survey(body: SurveyIn, current: dict = Depends(get_current_participant),
                      db: AsyncSession = Depends(get_db)):
    """TZ 2.1: specialization and industry from the survey define the category together with the test."""
    if body.specialization not in SPECIALIZATIONS or body.industry not in INDUSTRIES or \
            body.work_goal not in WORK_GOALS:
        raise ApiError(422, "validation_error", "Неизвестное значение в опросе")
    p = await db.get(Participant, _pid(current), with_for_update=True)
    if not p:
        raise HTTPException(404, "Профиль не найден")
    p.specialization, p.industry, p.work_goal = body.specialization, body.industry, body.work_goal
    p.declared_grade = body.declared_grade
    # The survey specialization is the main resume; an extra one in the same specialization goes.
    await db.execute(delete(CandidateResume).where(
        CandidateResume.participant_id == p.id, CandidateResume.specialization == p.specialization))
    if "salary_from_gross" in body.model_fields_set or "salary_to_gross" in body.model_fields_set:
        low, high = body.salary_from_gross, body.salary_to_gross
        if body.salary_basis == "net":
            from app.services.salary_net import gross_for_net
            low = gross_for_net(low) if low else low
            high = gross_for_net(high) if high else high
        if low and high and low > high:
            raise ApiError(422, "validation_error", "Зарплата «от» больше, чем «до»")
        p.salary_from_gross = low
        p.salary_to_gross = high
    if body.work_formats:
        p.work_formats = list(dict.fromkeys(body.work_formats))
    if body.region:
        from app.services.cities import city_name
        named = city_name(body.region)
        if named is None:
            raise ApiError(422, "validation_error", "Город выберите из справочника")
        p.region = named
    if p.category_opened_at is None:
        p.category_opened_at = datetime.now(UTC)
    p.profile_version = (p.profile_version or 0) + 1
    if body.experience_years is not None:
        p.experience_years = body.experience_years
    p.survey_at = datetime.now(UTC)
    # The confirmed grade shown on the card is the one for the chosen specialization.
    await sync_assessed_grade(db, p)
    await rebuild_profile(db, p)
    await db.commit()
    return {"ok": True, "specialization": p.specialization, "assessed_grade": p.assessed_grade}
