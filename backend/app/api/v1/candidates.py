import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_participant
from app.api.errors import ApiError
from app.api.v1.messages import unread_counts
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.models import AccessLog, CategoryAssignment, ConsentLog, GradeConfirmation, Offer, Participant
from app.models.participant import Result, Skill
from app.models.profile import DisciplineScore
from app.services.ai.assistant import parse_resume
from app.services.assessment import sync_assessed_grade
from app.services.categorization import DISCIPLINE_LABELS, GRADES
from app.services.fsp import identity as fsp_identity
from app.services.fsp.mock import get_fsp_adapter
from app.services.fsp.registry import FSPRegistryError
from app.services.identity import active_consent
from app.services.notify import Outbox, category_label, notify
from app.services.offers import expire_if_stale, expire_stale
from app.services.pdf_profile import extract_pdf_text, profile_lines, render_profile_pdf
from app.services.privacy import erase_participant
from app.services.profile import ingest_from_fsp, rebuild_profile
from app.services.scoring.engine import STATUS_LABELS, rank_equivalent
from app.services.skills import (
    SkillDraft,
    normalize_skill,
    plan_skill_replacement,
    read_resume_evidence,
    skill_line,
    with_resume_token,
)
from app.services.survey import INDUSTRIES, SPECIALIZATIONS, WORK_GOALS

router = APIRouter(prefix="/candidates", tags=["candidates"])

PRIVACY_FIELDS = ("is_visible", "public_profile")
_PAGE_SIZE_MAX = 50


def _skill_view(s: Skill) -> dict:
    return {"name": s.name, "trust_level": s.trust_level, "source_quote": s.source_quote,
            "confirmed": s.confirmed,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "confirmed_at": s.confirmed_at.isoformat() if s.confirmed_at else None}


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
        "email": p.email, "email_verified": p.email_verified_at is not None,
        "telegram": p.telegram, "phone": p.phone,
        "experience_years": p.experience_years, "declared_grade": p.declared_grade,
        "specialization": p.specialization, "industry": p.industry, "work_goal": p.work_goal,
        "survey_done": p.survey_at is not None,
        "confirmations": [{"specialization": c.specialization, "grade": c.grade, "p_pass": c.p_pass,
                           "confirmed_at": c.confirmed_at.isoformat(),
                           "locked_until": c.locked_until.isoformat() if c.locked_until else None}
                          for c in await db.scalars(select(GradeConfirmation).where(
                              GradeConfirmation.participant_id == p.id))],
        "assessed_grade": p.assessed_grade,
        "assessed_at": p.assessed_at.isoformat() if p.assessed_at else None,
        "grade_locked_until": p.grade_locked_until.isoformat() if p.grade_locked_until else None,
        "is_visible": p.is_visible, "public_profile": p.public_profile,
        "is_minor": p.is_minor, "minor_consent_given": p.minor_consent_given,
        "discoverable": p.discoverable,
        "primary_role": cat.primary_role if cat else None,
        "grade": cat.grade if cat else None,
        "grade_source": cat.grade_source if cat else None,
        "stack": cat.stack if cat else [],
        "explanation": cat.explanation if cat else [],
        "skills": [_skill_view(s) for s in p.skills],
        "discipline_scores": [
            {"discipline": ds.discipline, "label": DISCIPLINE_LABELS.get(ds.discipline, ds.discipline),
             "score": ds.score, "sigma": ds.sigma, "lcb": ds.lcb, "confidence": ds.confidence,
             "best_rank": ds.best_rank, "events_count": ds.events_count}
            for ds in sorted(p.discipline_scores, key=lambda d: -d.lcb)
        ],
        "results_count": len(p.results),
    }


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
    public_profile: bool | None = None
    is_visible: bool | None = None


@router.put("/me/profile")
async def update_profile(body: ProfileUpdate, current: dict = Depends(get_current_participant),
                         db: AsyncSession = Depends(get_db)):
    p = await db.get(Participant, _pid(current))
    if not p:
        raise HTTPException(404, "Профиль не найден")
    data = body.model_dump(exclude_unset=True)
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
    for field in PRIVACY_FIELDS:
        value = data.get(field)
        if value is None:
            continue
        if value != getattr(p, field):
            _log_privacy(db, p, field, value)
        setattr(p, field, value)
    for field in ("telegram", "phone"):
        if field in data:
            setattr(p, field, data[field] or None)
    if data.get("display_name"):
        p.display_name = data["display_name"].strip()
    if "region" in data and p.fsp_id is None:
        # With FSP linked, the region comes from the protocols.
        p.region = (data["region"] or "").strip() or None
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
    return {"is_visible": p.is_visible, "discoverable": p.discoverable}


class DeleteAccountIn(BaseModel):
    confirm: str = Field(..., max_length=20)


@router.delete("/me")
async def delete_my_account(body: DeleteAccountIn, current: dict = Depends(get_current_participant),
                            db: AsyncSession = Depends(get_db)):
    """Erase the account now (152-FZ, art. 21): contacts, name, FSP link and skills are removed,
    pending invitations are withdrawn. Anonymous sport results and the consent log stay."""
    if body.confirm.strip().lower() != "удалить":
        raise ApiError(422, "delete_confirm")
    p = await db.get(Participant, _pid(current))
    if not p or p.deleted_at is not None:
        raise HTTPException(404, "Профиль не найден")
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
        "rank_equivalent": rank_equivalent(r.competition_status, r.place, r.total_participants),
        "is_team": r.is_team, "team_size": r.team_size, "event_date": r.event_date.isoformat(),
        "protocol_url": r.protocol_url, "trust_level": r.trust_level,
    } for r in rows]


@router.get("/me/offers")
async def get_my_offers(
    limit: int = Query(20, ge=1, le=_PAGE_SIZE_MAX),
    offset: int = Query(0, ge=0),
    current: dict = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of offers sent to this candidate."""
    rows = list(await db.scalars(
        select(Offer)
        .where(Offer.candidate_id == _pid(current))
        .options(selectinload(Offer.employer))
        .order_by(Offer.created_at.desc())
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
    return [{
        "id": str(o.id), "company": o.employer.company_name, "role": o.role,
        # The company card the employer keeps (TZ: the candidate sees who invites). No personal data here.
        "company_profile": {"industry": o.employer.industry, "website": o.employer.website,
                            "about": o.employer.description, "inn_given": bool(o.employer.inn)},
        "contact_method": o.contact_method,
        "salary_from": o.salary_from_gross, "salary_to": o.salary_to_gross,
        "currency": o.currency, "work_format": o.work_format, "message": o.message,
        "status": o.status, "created_at": o.created_at.isoformat(),
        "expires_at": o.expires_at.isoformat() if o.expires_at else None,
        "contacts_revoked_at": o.contacts_revoked_at.isoformat() if o.contacts_revoked_at else None,
        "unread_messages": unread.get(o.id, 0),
    } for o in rows]


class RespondIn(BaseModel):
    action: Literal["accept", "reject"]


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
        offer.contacts_revealed_at = datetime.now(UTC)
        db.add(ConsentLog(participant_id=offer.candidate_id, event_type="contacts_revealed",
                          actor_id=offer.candidate_id, meta={"offer_id": str(offer.id)}))
    else:
        offer.status = "rejected"
        db.add(ConsentLog(participant_id=offer.candidate_id, event_type="offer_rejected",
                          actor_id=offer.candidate_id, meta={"offer_id": str(offer.id)}))
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
    await db.commit()
    await outbox.deliver()
    return {"status": offer.status}


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
    await db.commit()
    await outbox.deliver()
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
    data = await file.read()
    try:
        text = extract_pdf_text(data)
    except ValueError as e:
        raise ApiError(422, "validation_error", "Нужен обычный PDF не больше 5 МБ") from e
    if not text:
        raise ApiError(422, "validation_error", "В PDF не нашлось текста")
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
        [{"label": DISCIPLINE_LABELS.get(s.discipline, s.discipline), "lcb": s.lcb, "rank": s.best_rank}
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
                    headers={"Content-Disposition": "attachment; filename=profile.pdf"})


@router.get("/survey-options")
async def survey_options():
    """Choices for the survey; public, so the registration flow can show them before login."""
    return {"specializations": SPECIALIZATIONS, "industries": INDUSTRIES, "work_goals": WORK_GOALS,
            "grades": list(GRADES)}


class SurveyIn(BaseModel):
    specialization: str
    # The subject area (fintech, retail…) is optional: the IT direction is the specialization itself.
    industry: str = "any"
    work_goal: str = "job"
    declared_grade: Literal["intern", "junior", "middle", "senior", "lead"] | None = None
    experience_years: int | None = Field(None, ge=0, le=50)


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
    if body.declared_grade is not None:
        p.declared_grade = body.declared_grade
    elif body.work_goal == "internship" and not p.declared_grade:
        p.declared_grade = "intern"
    if body.experience_years is not None:
        p.experience_years = body.experience_years
    p.survey_at = datetime.now(UTC)
    # The confirmed grade shown on the card is the one for the chosen specialization.
    await sync_assessed_grade(db, p)
    await rebuild_profile(db, p)
    await db.commit()
    return {"ok": True, "specialization": p.specialization, "assessed_grade": p.assessed_grade}
