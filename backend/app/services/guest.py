"""Guest accounts of the demo stand: try either cabinet without a mailbox.

A guest gets a fresh empty account for 48 hours, after the same required consents as a registration.
A guest candidate never enters the employer search or the bank, so the jury base stays as published.
A guest company has a placeholder address in the reserved .invalid zone: no letter leaves for it.
When the time is up the sessions close; the hourly purge erases candidates the way account deletion
does, withdraws the company's pending invitations and closes its vacancies. Off unless DEMO_MODE is on.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employer, Offer, Participant, Vacancy
from app.services.privacy import erase_participant

GUEST_TTL = timedelta(hours=48)
GUEST_DOMAIN = "guest.invalid"
GUEST_COMPANY = "Гостевая компания"


def guest_expired(account, now: datetime | None = None) -> bool:
    until = getattr(account, "guest_until", None)
    return until is not None and until <= (now or datetime.now(UTC))


def new_guest(role: str, now: datetime | None = None) -> Participant | Employer:
    until = (now or datetime.now(UTC)) + GUEST_TTL
    if role == "participant":
        return Participant(email=None, display_name="Гость", is_visible=False, public_profile=False,
                           is_minor=False, guest_until=until)
    return Employer(company_name=GUEST_COMPANY, email=f"guest-{secrets.token_hex(6)}@{GUEST_DOMAIN}",
                    password_hash="!", email_verified_at=now or datetime.now(UTC), guest_until=until)


async def purge_guests(db: AsyncSession, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    erased = 0
    for person in await db.scalars(select(Participant).where(
            Participant.guest_until <= now, Participant.deleted_at.is_(None))):
        await erase_participant(db, person, reason="guest_expired")
        erased += 1
    expired = select(Employer.id).where(Employer.guest_until <= now)
    offers = await db.execute(update(Offer).where(Offer.employer_id.in_(expired), Offer.status == "pending")
                              .values(status="withdrawn"))
    vacancies = await db.execute(update(Vacancy).where(Vacancy.employer_id.in_(expired), Vacancy.is_open.is_(True))
                                 .values(is_open=False))
    return erased + (offers.rowcount or 0) + (vacancies.rowcount or 0)
