"""S2: the additive top-up fills a juror's missing birth date and never overwrites one that is set."""
from datetime import date

from sqlalchemy import select

from app.models import Participant
from app.models.participant import adult_confirmed
from seed.generate_seed import JURY_BIRTH
from seed.topup_public import backfill_jury
from tests.integration.conftest import PASSWORD_HASH, now, wipe_people


async def _jury7(db) -> tuple[Participant, bool]:
    for person in await db.scalars(select(Participant).where(Participant.email.is_not(None))):
        if person.email == "jury7@demo.talent":
            return person, False
    person = Participant(email="jury7@demo.talent", display_name="Член жюри 7", password_hash=PASSWORD_HASH,
                         email_verified_at=now(), is_minor=False, is_visible=True, public_profile=False)
    db.add(person)
    await db.commit()
    return person, True


async def test_backfill_fills_only_missing_fields(db):
    person, created = await _jury7(db)
    kept = person.birth_date
    try:
        person.birth_date = None
        await db.commit()
        assert await backfill_jury(db) >= 1
        await db.refresh(person)
        assert person.birth_date == JURY_BIRTH and adult_confirmed(person)
        person.birth_date = date(1985, 1, 2)
        await db.commit()
        await backfill_jury(db)
        await db.refresh(person)
        assert person.birth_date == date(1985, 1, 2)  # never overwritten
    finally:
        if created:
            await wipe_people([person.id])
        else:
            person.birth_date = kept
            await db.commit()
