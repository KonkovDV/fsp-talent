import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.models import AccessLog, Employer, Offer, Participant
from app.services.offers import expire_if_stale, expire_stale

router = APIRouter(prefix="/offers", tags=["offers"])

_OFFERS_PER_DAY = 50


def _eid(current: dict) -> uuid.UUID:
    return uuid.UUID(current["sub"])


class OfferCreate(BaseModel):
    candidate_id: uuid.UUID
    salary_from_gross: int = Field(gt=0, le=100_000_000)
    salary_to_gross: int = Field(gt=0, le=100_000_000)
    currency: Literal["RUB"] = "RUB"
    role: str = Field(min_length=2, max_length=100)
    work_format: Literal["remote", "office", "hybrid"] = "remote"
    message: str | None = Field(None, max_length=2000)
    # TZ 2.2 п.2: how the candidate reaches the company (email, Telegram, phone of the recruiter).
    contact_method: str = Field(min_length=3, max_length=300)

    @model_validator(mode="after")
    def _range(self):
        if self.salary_to_gross < self.salary_from_gross:
            raise ValueError("Верхняя граница зарплаты меньше нижней")
        return self


def _offer_out(o: Offer) -> dict:
    return {
        "id": str(o.id), "candidate_id": str(o.candidate_id), "role": o.role,
        "salary_from": o.salary_from_gross, "salary_to": o.salary_to_gross,
        "currency": o.currency, "work_format": o.work_format, "message": o.message,
        "status": o.status, "created_at": o.created_at.isoformat(),
        "expires_at": o.expires_at.isoformat() if o.expires_at else None,
        "contact_method": o.contact_method,
        "candidate_viewed_at": o.candidate_viewed_at.isoformat() if o.candidate_viewed_at else None,
        "contacts_available": o.status == "accepted",
        # FIX BUG-A: expose contacts_revealed_at so the audit trail is queryable via API
        "contacts_revealed_at": o.contacts_revealed_at.isoformat() if o.contacts_revealed_at else None,
    }


@router.post("/", status_code=201)
async def create_offer(body: OfferCreate, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    employer = await db.get(Employer, _eid(current))
    if not employer:
        raise HTTPException(404, "Работодатель не найден")
    # Employers are not verified in the MVP: cap how many people one account can message per day.
    if await too_many(f"offers:create:{employer.id}", limit=_OFFERS_PER_DAY, window_seconds=86_400):
        raise HTTPException(429, "Лимит приглашений на сегодня исчерпан")
    candidate = await db.get(Participant, body.candidate_id)
    if not candidate or not candidate.discoverable:
        raise HTTPException(404, "Кандидат недоступен для предложений")
    pending = await db.scalar(select(Offer).where(
        Offer.employer_id == employer.id, Offer.candidate_id == candidate.id, Offer.status == "pending"))
    if pending and expire_if_stale(pending):
        await db.flush()
        pending = None
    if pending:
        raise HTTPException(409, "Активный оффер этому кандидату уже есть")
    offer = Offer(
        employer_id=employer.id, candidate_id=candidate.id,
        salary_from_gross=body.salary_from_gross, salary_to_gross=body.salary_to_gross,
        currency=body.currency, role=body.role, work_format=body.work_format, message=body.message,
        contact_method=body.contact_method.strip(),
        status="pending", expires_at=datetime.now(UTC) + timedelta(days=14),
    )
    db.add(offer)
    try:
        # uq_offers_pending_pair (migration 0002) closes the check-then-insert race.
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(409, "Активный оффер этому кандидату уже есть") from e
    await db.commit()
    return _offer_out(offer)


@router.get("/")
async def list_my_offers(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(
        select(Offer).where(Offer.employer_id == _eid(current)).order_by(Offer.created_at.desc())))
    if expire_stale(rows):
        await db.commit()
    return [_offer_out(o) for o in rows]


@router.post("/{offer_id}/withdraw")
async def withdraw_offer(offer_id: uuid.UUID, current: dict = Depends(get_current_employer),
                         db: AsyncSession = Depends(get_db)):
    # Same lock as the candidate side: withdraw and accept cannot both win.
    offer = await db.get(Offer, offer_id, with_for_update=True)
    if not offer or offer.employer_id != _eid(current):
        raise HTTPException(404, "Оффер не найден")
    if offer.status != "pending":
        raise HTTPException(409, "Отозвать можно только ожидающий оффер")
    offer.status = "withdrawn"
    await db.commit()
    return {"status": offer.status}


@router.get("/{offer_id}/contacts")
async def reveal_contacts(offer_id: uuid.UUID, current: dict = Depends(get_current_employer),
                          db: AsyncSession = Depends(get_db)):
    offer = await db.get(Offer, offer_id)
    if not offer or offer.employer_id != _eid(current):
        raise HTTPException(404, "Оффер не найден")
    if offer.status != "accepted":
        raise HTTPException(403, "Контакты открываются только после согласия кандидата")
    candidate = await db.get(Participant, offer.candidate_id)
    if not candidate:
        raise HTTPException(404, "Кандидат не найден")
    # FIX BUG-A: stamp contacts_revealed_at on first reveal; idempotent on repeated calls.
    now = datetime.now(UTC)
    if offer.contacts_revealed_at is None:
        offer.contacts_revealed_at = now
    db.add(AccessLog(employer_id=offer.employer_id, participant_id=candidate.id, access_type="contacts_view"))
    await db.commit()
    return {
        "candidate_id": str(candidate.id), "display_name": candidate.display_name,
        "email": candidate.email, "telegram": candidate.telegram,
        "phone": candidate.phone, "region": candidate.region,
        "contacts_revealed_at": offer.contacts_revealed_at.isoformat(),
    }
