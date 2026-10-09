"""Hold on new invitations when complaints from different people are not a one-off.

The share is complaints divided by invitations over 30 days. The lower Wilson bound
(z = 1.64) must reach 0.10, and the complaints must come from at least three candidates.
Releasing the hold is a manual command; this module does not delete the complaints.
"""
from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select

from app.services.matching import wilson_lower

WINDOW_DAYS = 30
MIN_DISTINCT = 3
MIN_LCB = 0.10
Z = 1.64


def should_pause(distinct_candidates: int, complaints: int, invitations: int) -> bool:
    """True when the company should stop sending invitations until someone releases it."""
    if distinct_candidates < MIN_DISTINCT or invitations <= 0 or complaints <= 0:
        return False
    lower = wilson_lower(complaints, invitations, z=Z)
    return lower is not None and lower >= MIN_LCB


def complaints_that_count(emails: list[str | None]) -> list[str]:
    """Drop complaints from demo accounts. On a real stand every complaint counts."""
    from app.core.demo_guard import is_protected

    return [email for email in emails if email and not is_protected(email)]


async def refresh_hold(db, employer_id: uuid.UUID) -> bool:
    """Set the hold if the rule is met. A hold that is already set stays until release."""
    from app.models import Complaint, Employer, Offer, Participant, Vacancy

    since = datetime.now(UTC) - timedelta(days=WINDOW_DAYS)
    rows = (await db.execute(
        select(Participant.id, Participant.email)
        .select_from(Complaint)
        .join(Participant, Participant.id == Complaint.participant_id)
        .outerjoin(Offer, Complaint.offer_id == Offer.id)
        .outerjoin(Vacancy, Complaint.vacancy_id == Vacancy.id)
        .where(Complaint.created_at >= since,
               or_(Offer.employer_id == employer_id, Vacancy.employer_id == employer_id))
    )).all()
    from app.services.field_cipher import PREFIX, open_seal
    emails = []
    for pid, stored in rows:
        if isinstance(stored, str) and stored.startswith(PREFIX):
            try:
                emails.append(open_seal(str(pid), "participants", "email", stored))
            except Exception:
                continue
        else:
            emails.append(stored)
    counted = complaints_that_count(emails)
    invitations = await db.scalar(select(func.count()).select_from(Offer).where(
        Offer.employer_id == employer_id, Offer.created_at >= since)) or 0
    if not should_pause(len(set(counted)), len(counted), int(invitations)):
        return False
    employer = await db.get(Employer, employer_id)
    if employer is None:
        return False
    if employer.invites_paused_at is None:
        employer.invites_paused_at = datetime.now(UTC)
    return True


async def release_invites(inn: str) -> int:
    """Clear the hold for every company with this tax id. Returns how many were waiting."""
    from app.core.database import AsyncSessionLocal
    from app.core.rls import bypass_rls
    from app.models import Employer

    bypass_rls()
    inn = inn.strip()
    async with AsyncSessionLocal() as db:
        rows = list(await db.scalars(select(Employer).where(
            Employer.inn == inn, Employer.invites_paused_at.is_not(None))))
        for employer in rows:
            employer.invites_paused_at = None
        await db.commit()
        return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Снять паузу приглашений после проверки")
    parser.add_argument("command", choices=("release",))
    parser.add_argument("inn")
    args = parser.parse_args()
    found = asyncio.run(release_invites(args.inn))
    if found:
        print(f"Приглашения снова можно отправлять: компаний {found}, ИНН {args.inn.strip()}")
    else:
        print(f"Компания с ИНН {args.inn.strip()} не стоит на проверке")


if __name__ == "__main__":
    main()
