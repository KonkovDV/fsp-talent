"""
Candidate-facing endpoints: view incoming offers and respond to them.

Business rules
--------------
* A candidate may only see offers addressed to them.
* Acceptance reveals contact details to the employer (logged in consent_logs).
* Rejection is also logged for audit trail and GDPR compliance.
* Expired offers are lazily marked as 'expired' on next list view.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_participant
from app.models.consent_log import ConsentLog
from app.models.offer import Offer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["candidates"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class OfferSummary(BaseModel):
    id: UUID
    employer_id: UUID
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


class RespondBody(BaseModel):
    action: str  # "accept" | "reject"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/offers", response_model=list[OfferSummary])
async def list_offers(
    participant=Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
) -> list[OfferSummary]:
    """List all offers received by the current candidate."""
    rows = await db.scalars(
        select(Offer)
        .where(Offer.candidate_id == participant.id)
        .order_by(Offer.created_at.desc())
    )
    offers = list(rows)

    # Lazy expiry: mark stale pending offers without a background job
    now = datetime.now(timezone.utc)
    changed = False
    for offer in offers:
        if offer.status == "pending" and offer.expires_at < now:
            offer.status = "expired"
            changed = True
    if changed:
        await db.commit()

    return [OfferSummary.model_validate(o) for o in offers]


@router.post("/offers/{offer_id}/respond", response_model=OfferSummary)
async def respond_to_offer(
    offer_id: UUID,
    body: RespondBody,
    participant=Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
) -> OfferSummary:
    """Accept or reject an incoming offer.

    Both actions are written to consent_logs for audit / GDPR compliance.
    Only participant_id is stored -- no personal contact data.
    """
    if body.action not in ("accept", "reject"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="action dolzhen byt' 'accept' ili 'reject'.",
        )

    offer: Offer | None = await db.get(Offer, offer_id)
    if not offer or offer.candidate_id != participant.id:
        raise HTTPException(status_code=404, detail="Predlozhenie ne naydeno.")

    if offer.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Predlozhenie uzhe obrabotano: {offer.status}.",
        )

    now = datetime.now(timezone.utc)
    if offer.expires_at < now:
        offer.status = "expired"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Srok dejstviya predlozheniya istek.",
        )

    if body.action == "accept":
        offer.status = "accepted"
        db.add(
            ConsentLog(
                participant_id=participant.id,
                actor_id=participant.id,
                action="offer_accepted",
                offer_id=offer.id,
            )
        )
        logger.info(
            "Offer accepted participant=%s offer=%s employer=%s",
            participant.id,
            offer.id,
            offer.employer_id,
        )
    else:  # reject
        offer.status = "rejected"
        # Log rejection: important for GDPR audit trail (right to know)
        db.add(
            ConsentLog(
                participant_id=participant.id,
                actor_id=participant.id,
                action="offer_rejected",
                offer_id=offer.id,
            )
        )
        logger.info(
            "Offer rejected participant=%s offer=%s employer=%s",
            participant.id,
            offer.id,
            offer.employer_id,
        )

    await db.commit()
    await db.refresh(offer)
    return OfferSummary.model_validate(offer)
