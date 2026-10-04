import uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_participant
from app.core.database import get_db
from app.models import ConsentLog, Offer, Participant
from app.models.participant import Result, Skill
from app.services.categorization import DISCIPLINE_LABELS, GRADES
from app.services.offers import expire_if_stale, expire_stale
from app.services.profile import rebuild_profile
from app.services.scoring.engine import STATUS_LABELS, rank_equivalent
from app.services.skills import normalize_skill

router = APIRouter(prefix="/candidates", tags=["candidates"])

# Privacy switches whose changes are written to consent_logs (152-FZ art. 9, 10.1).
PRIVACY_FIELDS = ("is_visible", "public_profile")


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
    if not p:
        raise HTTPException(404, "Профиль не найден")
    cat = p.category
    return {
        "id": str(p.id), "fsp_id": p.fsp_id, "display_name": p.display_name, "region": p.region,
        "email": p.email, "telegram": p.telegram, "phone": p.phone,
        "experience_years": p.experience_years, "declared_grade": p.declared_grade,
        "is_visible": p.is_visible, "public_profile": p.public_profile,
        "is_minor": p.is_minor, "minor_consent_given": p.minor_consent_given,
        "discoverable": p.discoverable,
        "primary_role": cat.primary_role if cat else None,
        "grade": cat.grade if cat else None,
        "grade_source": cat.grade_source if cat else None,
        "stack": cat.stack if cat else [],
        "explanation": cat.explanation if cat else [],
        "skills": [{"name": s.name, "trust_level": s.trust_level, "source_quote": s.source_quote,
                    "confirmed": s.confirmed} for s in p.skills],
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
    declared_grade: Literal["junior", "middle", "senior", "lead"] | None = None
    skills: list[SkillIn] | None = Field(None, max_length=40)
    email: EmailStr | None = None
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
    if data.get("public_profile") and p.is_minor:
        raise HTTPException(403, "Именная страница недоступна для несовершеннолетних")
    if "declared_grade" in data and data["declared_grade"] not in (*GRADES, None):
        raise HTTPException(400, "Неизвестный грейд")
    for field in ("experience_years", "declared_grade"):
        if field in data:
            setattr(p, field, data[field])
    for field in PRIVACY_FIELDS:
        value = data.get(field)
        if value is None:  # columns are NOT NULL; null means "leave as is"
            continue
        if value != getattr(p, field):
            _log_privacy(db, p, field, value)
        setattr(p, field, value)
    for field in ("email", "telegram", "phone"):
        if field in data:
            setattr(p, field, data[field] or None)
    if "skills" in data:
        seen: set[str] = set()
        rows = []
        for item in data["skills"]:
            canonical = normalize_skill(item["name"])
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)
            quote = (item.get("source_quote") or "").strip() or None
            rows.append(Skill(participant_id=p.id, name=canonical, raw_name=item["name"][:200],
                              source_quote=quote,
                              trust_level="resume_confirmed" if quote else "self_reported", confirmed=True))
        await db.execute(delete(Skill).where(Skill.participant_id == p.id))
        await db.flush()
        db.add_all(rows)
    try:
        await db.flush()
    except IntegrityError as e:
        raise HTTPException(409, "Такой email уже используется") from e
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


@router.get("/me/results")
async def get_my_results(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Result).where(Result.participant_id == _pid(current)).order_by(Result.event_date.desc()))
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
async def get_my_offers(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(
        select(Offer).where(Offer.candidate_id == _pid(current)).options(selectinload(Offer.employer))
        .order_by(Offer.created_at.desc())))
    changed = expire_stale(rows)
    if changed:
        await db.commit()
    return [{
        "id": str(o.id), "company": o.employer.company_name, "role": o.role,
        "salary_from": o.salary_from_gross, "salary_to": o.salary_to_gross,
        "currency": o.currency, "work_format": o.work_format, "message": o.message,
        "status": o.status, "created_at": o.created_at.isoformat(),
        "expires_at": o.expires_at.isoformat() if o.expires_at else None,
    } for o in rows]


class RespondIn(BaseModel):
    action: Literal["accept", "reject"]


@router.post("/me/offers/{offer_id}/respond")
async def respond_to_offer(offer_id: uuid.UUID, body: RespondIn, current: dict = Depends(get_current_participant),
                           db: AsyncSession = Depends(get_db)):
    # Row lock: two concurrent accept/reject requests are serialized, the second one sees
    # status != pending and gets 409 instead of writing a duplicate consent event.
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
        offer.contacts_revealed_at = datetime.now(timezone.utc)
        db.add(ConsentLog(participant_id=offer.candidate_id, event_type="contacts_revealed",
                          actor_id=offer.candidate_id, meta={"offer_id": str(offer.id)}))
    else:
        offer.status = "rejected"
        db.add(ConsentLog(participant_id=offer.candidate_id, event_type="offer_rejected",
                          actor_id=offer.candidate_id, meta={"offer_id": str(offer.id)}))
    await db.commit()
    return {"status": offer.status}
