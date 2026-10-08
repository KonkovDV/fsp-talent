"""Messages after an accepted invitation: a short thread so both sides can talk on the platform.

Only the two sides of the invitation read the thread. It opens when the candidate accepts; after the
candidate closes the contacts for the company, the thread stays readable but nobody can post.
The other side gets a bell row; the letter says only that a message arrived, never its text.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_any_auth
from app.api.errors import ApiError
from app.core.database import get_db
from app.core.ratelimit import RateLimitUnavailable, too_many
from app.models import Employer, Offer, OfferMessage
from app.services.notify import Outbox, notify

router = APIRouter(prefix="/offers", tags=["messages"])

MESSAGES_PER_HOUR = 60


def thread_side(offer: Offer, role: str | None, subject: uuid.UUID) -> str | None:
    """The side the caller is on in this invitation, or None if it is not theirs."""
    if role == "participant" and offer.candidate_id == subject:
        return "participant"
    if role == "employer" and offer.employer_id == subject:
        return "employer"
    return None


def can_post(offer: Offer) -> bool:
    return offer.status == "accepted" and offer.contacts_revoked_at is None


async def _offer_for(db: AsyncSession, offer_id: uuid.UUID, current: dict) -> tuple[Offer, str]:
    offer = await db.get(Offer, offer_id)
    side = thread_side(offer, current.get("role"), uuid.UUID(current["sub"])) if offer else None
    if offer is None or side is None:
        raise ApiError(404, "not_found", "Приглашение не найдено")
    if offer.status != "accepted":
        raise ApiError(403, "contacts_hidden", "Переписка открывается, когда кандидат принимает приглашение")
    return offer, side


def _view(m: OfferMessage, side: str) -> dict:
    return {"id": str(m.id), "mine": m.author_role == side, "author": m.author_role, "body": m.body,
            "created_at": m.created_at.isoformat(), "read": m.read_at is not None}


@router.get("/{offer_id}/messages")
async def list_messages(offer_id: uuid.UUID, current: dict = Depends(get_any_auth),
                        db: AsyncSession = Depends(get_db)):
    offer, side = await _offer_for(db, offer_id, current)
    rows = list(await db.scalars(select(OfferMessage).where(OfferMessage.offer_id == offer.id)
                                 .order_by(OfferMessage.created_at).limit(500)))
    await db.execute(update(OfferMessage).where(OfferMessage.offer_id == offer.id, OfferMessage.author_role != side,
                                                OfferMessage.read_at.is_(None))
                     .values(read_at=datetime.now(UTC)))
    await db.commit()
    return {"can_post": can_post(offer), "messages": [_view(m, side) for m in rows]}


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.post("/{offer_id}/messages", status_code=201)
async def post_message(offer_id: uuid.UUID, body: MessageIn, current: dict = Depends(get_any_auth),
                       db: AsyncSession = Depends(get_db)):
    offer, side = await _offer_for(db, offer_id, current)
    if not can_post(offer):
        raise ApiError(403, "contacts_revoked", "Кандидат закрыл контакты для компании: переписка только для чтения")
    text = body.body.strip()
    if not text:
        raise ApiError(422, "validation_error", "Пустое сообщение")
    try:
        if await too_many(f"messages:{side}:{current['sub']}", limit=MESSAGES_PER_HOUR, window_seconds=3600,
                          fail_closed=True):
            raise ApiError(429, "rate_limited", "Слишком много сообщений, подождите")
    except RateLimitUnavailable as e:
        raise ApiError(503, "unavailable", "Лимит сообщений сейчас недоступен") from e
    message = OfferMessage(offer_id=offer.id, author_role=side, body=text, created_at=datetime.now(UTC))
    db.add(message)
    outbox = Outbox()
    if side == "employer":
        company = await db.scalar(select(Employer.company_name).where(Employer.id == offer.employer_id))
        await notify(db, outbox, "participant", offer.candidate_id, "message_new",
                     f"Сообщение от «{company}»", f"Новое сообщение по приглашению «{offer.role}».",
                     f"/candidate/offers?thread={offer.id}")
    else:
        await notify(db, outbox, "employer", offer.employer_id, "message_new",
                     f"Сообщение от кандидата по «{offer.role}»", "Кандидат написал в переписке по приглашению.",
                     f"/employer/offers?thread={offer.id}")
    await db.commit()
    await outbox.deliver()
    return _view(message, side)


async def unread_counts(db: AsyncSession, offer_ids: list[uuid.UUID], side: str) -> dict[uuid.UUID, int]:
    """Unread messages from the other side, per invitation, for the lists of both cabinets."""
    if not offer_ids:
        return {}
    rows = await db.execute(select(OfferMessage.offer_id, func.count()).where(
        OfferMessage.offer_id.in_(offer_ids), OfferMessage.author_role != side, OfferMessage.read_at.is_(None))
        .group_by(OfferMessage.offer_id))
    return dict(rows.all())
