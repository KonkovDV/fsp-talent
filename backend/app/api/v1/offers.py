import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_employer
from app.core.database import get_db
from app.models import AccessLog, Employer, Offer, Participant
from app.services.offers import expire_if_stale

router = APIRouter(prefix="/offers", tags=["offers"])


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
        "contacts_available": o.status == "accepted",
    }


@router.post("/", status_code=201)
async def create_offer(body: OfferCreate, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    employer = await db.get(Employer, _eid(current))
    if not employer:
        raise HTTPException(404, "Работодатель не найден")
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
        status="pending", expires_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db.add(offer)
    await db.flush()
    await db.commit()
    return _offer_out(offer)


@router.get("/")
async def list_my_offers(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(Offer).where(Offer.employer_id == _eid(current)).order_by(Offer.created_at.desc())))
    if any(expire_if_stale(o) for o in rows):
        await db.commit()
    return [_offer_out(o) for o in rows]


@router.post("/{offer_id}/withdraw")
async def withdraw_offer(offer_id: uuid.UUID, current: dict = Depends(get_current_employer),
                         db: AsyncSession = Depends(get_db)):
    offer = await db.get(Offer, offer_id)
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
    db.add(AccessLog(employer_id=offer.employer_id, participant_id=candidate.id, access_type="contacts_view"))
    await db.commit()
    return {
        "candidate_id": str(candidate.id), "display_name": candidate.display_name,
        "email": candidate.email, "telegram": candidate.telegram, "phone": candidate.phone, "region": candidate.region,
    }
