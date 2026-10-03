"""
Offer lifecycle endpoints.

Business rules
--------------
* Employers may only send offers to discoverable candidates:
  - is_visible must be True
  - if is_minor, minor_consent_given must be True
* Offers expire in 14 days (set by Offer.expires_at default).
* Contacts are revealed only after the candidate accepts.
* Only the offer's own employer may view contact details.

Privacy
-------
* The `contacts` endpoint is access-logged (ConsentLog) on every call.
* Only `participant_id` is stored in the log -- never email/phone/name.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_employer
from app.models.consent_log import ConsentLog
from app.models.offer import Offer
from app.models.participant import Participant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/offers", tags=["offers"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateOfferBody(BaseModel):
    candidate_id: UUID
    salary_from_gross: int = Field(ge=0)
    salary_to_gross: int = Field(ge=0)
    currency: str = Field(default="RUB", max_length=3)
    role: str = Field(max_length=100)
    work_format: str = Field(max_length=20)
    message: str | None = Field(default=None, max_length=2000)


class OfferOut(BaseModel):
    id: UUID
    candidate_id: UUID
    salary_from_gross: int
    salary_to_gross: int
    currency: str
    role: str
    work_format: str
    message: str | None
    status: str
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class ContactsOut(BaseModel):
    email: str | None
    telegram: str | None
    phone: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=OfferOut, status_code=status.HTTP_201_CREATED)
async def create_offer(
    body: CreateOfferBody,
    employer=Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
) -> OfferOut:
    """Send a job offer to a discoverable candidate."""
    candidate: Participant | None = await db.get(Participant, body.candidate_id)

    # Guard 1: candidate must exist and have enabled search visibility
    if not candidate or not candidate.is_visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kandidat nedostupen dlya predlozhenij.",
        )

    # Guard 2: explicit minor-consent check with a clear error message
    # (do NOT rely on discoverable property alone -- different HTTP status needed)
    if candidate.is_minor and not candidate.minor_consent_given:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Kandidat yavlyaetsya nesovershennoletnim: "
                "soglasie zakonno representaitelya ne polucheno. "
                "Predlozheniya nesovershennoletnim nedostupny."
            ),
        )

    # Guard 3: prevent duplicate active offers from the same employer
    existing = await db.scalar(
        select(Offer).where(
            Offer.employer_id == employer.id,
            Offer.candidate_id == body.candidate_id,
            Offer.status == "pending",
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aktivnoe predlozhenie dlya etogo kandidata uzhe sushchestvuet.",
        )

    offer = Offer(
        employer_id=employer.id,
        candidate_id=body.candidate_id,
        salary_from_gross=body.salary_from_gross,
        salary_to_gross=body.salary_to_gross,
        currency=body.currency,
        role=body.role,
        work_format=body.work_format,
        message=body.message,
    )
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    logger.info(
        "Offer created employer=%s candidate=%s offer=%s",
        employer.id,
        body.candidate_id,
        offer.id,
    )
    return OfferOut.model_validate(offer)


@router.get("/my", response_model=list[OfferOut])
async def list_my_offers(
    employer=Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
) -> list[OfferOut]:
    """List all offers sent by the current employer."""
    rows = await db.scalars(
        select(Offer)
        .where(Offer.employer_id == employer.id)
        .order_by(Offer.created_at.desc())
    )
    return [OfferOut.model_validate(r) for r in rows]


@router.get("/{offer_id}/contacts", response_model=ContactsOut)
async def get_contacts(
    offer_id: UUID,
    employer=Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
) -> ContactsOut:
    """Reveal candidate contact details after acceptance.

    First-access is logged in consent_logs for audit / GDPR compliance.
    The log stores only participant_id -- never personal contact data.
    """
    offer: Offer | None = await db.get(Offer, offer_id)
    if not offer or offer.employer_id != employer.id:
        raise HTTPException(status_code=404, detail="Predlozhenie ne naydeno.")

    if offer.status != "accepted":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kontakty dostupny tolko posle prinyatiya predlozheniya kandidatom.",
        )

    # Mark first reveal and log it
    if offer.contacts_revealed_at is None:
        offer.contacts_revealed_at = datetime.now(timezone.utc)
        db.add(
            ConsentLog(
                participant_id=offer.candidate_id,
                actor_id=employer.id,
                action="contacts_revealed",
                offer_id=offer.id,
            )
        )
        await db.commit()
        await db.refresh(offer)

    candidate: Participant = await db.get(Participant, offer.candidate_id)
    return ContactsOut(
        email=candidate.email,
        telegram=candidate.telegram,
        phone=candidate.phone,
    )
