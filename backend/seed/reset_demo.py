"""Return the jury stand to the state the three-minute show starts from.

Passwords of the published accounts go back to the printed one, jury surveys and tests
are cleared, and the show invitations are pending again. Refuses outside the demo stand.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.demo_guard import is_protected
from app.core.security import hash_password
from app.models import (
    Employer,
    Participant,
)
from app.services.demo_reset import clear_jury, restore_consents
from seed.demo_activity import restore_pending_invites
from seed.generate_seed import DEMO_PASSWORD, JURY_BIRTH


def refuse_outside_demo() -> None:
    if os.environ.get("ENV", "").lower() == "production":
        raise SystemExit("Сброс демо-стенда не выполняется, когда ENV=production")
    if not settings.DEMO_MODE:
        raise SystemExit("Сброс демо-стенда выполняется только при DEMO_MODE")


async def reset_demo() -> None:
    refuse_outside_demo()
    from app.core.rls import bypass_rls
    bypass_rls()
    password_hash = hash_password(DEMO_PASSWORD)
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        people = list(await db.scalars(select(Participant).where(Participant.email.is_not(None))))
        jury = 0
        for person in people:
            if not is_protected(person.email):
                continue
            person.password_hash = password_hash
            person.token_epoch = int(person.token_epoch or 0) + 1
            person.refresh_nonce = int(person.refresh_nonce or 0) + 1
            await restore_consents(db, person, now)
            if (person.email or "").startswith("jury") and person.email.endswith("@demo.talent"):
                if person.birth_date is None:
                    person.birth_date = JURY_BIRTH
                    person.is_minor = False
                await clear_jury(db, person)
                jury += 1
        companies = 0
        for company in await db.scalars(select(Employer).where(Employer.email.is_not(None))):
            if not is_protected(company.email):
                continue
            company.password_hash = password_hash
            company.token_epoch = int(company.token_epoch or 0) + 1
            company.refresh_nonce = int(company.refresh_nonce or 0) + 1
            company.invites_paused_at = None
            companies += 1
        invites = await restore_pending_invites(db)
        await db.commit()
        print(f"demo reset jury={jury} companies={companies} invites={invites}")


def main() -> None:
    asyncio.run(reset_demo())


if __name__ == "__main__":
    main()
