"""Stand audit S4: a saved birth date cannot be moved by the user, so a minor cannot become an adult."""
from __future__ import annotations

from datetime import date

import pytest

from app.api.errors import ApiError
from app.api.v1.candidates import ProfileUpdate, update_profile
from app.models import Participant
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def test_a_minor_cannot_move_the_birth_date_to_adult(db):
    today = date.today()
    minor_born = date(today.year - 16, 1, 1)
    person = Participant(email=f"dbtest-minor-{stamp()}@example.com", display_name="Несовершеннолетний",
                         password_hash=PASSWORD_HASH, email_verified_at=now(), is_minor=True,
                         birth_date=minor_born, is_visible=True, public_profile=False, minor_consent_given=False)
    db.add(person)
    await db.commit()
    pid = person.id
    current = {"sub": str(pid)}
    try:
        with pytest.raises(ApiError) as locked:
            await update_profile(ProfileUpdate(birth_date=date(today.year - 30, 1, 1)), current, db)
        assert locked.value.status_code == 409 and locked.value.code == "birth_date_locked"
        await db.rollback()
        fresh = await db.get(Participant, pid)
        await db.refresh(fresh)
        assert fresh.birth_date == minor_born and fresh.is_minor
        # The same date again is not a change.
        await update_profile(ProfileUpdate(birth_date=minor_born), current, db)
    finally:
        await db.rollback()
        await wipe_people([pid])


async def test_setting_the_birth_date_is_logged(db):
    """SEC3-04: the first saved date (it decides the guardian's consent and 18+) leaves a ConsentLog entry."""
    from sqlalchemy import select

    from app.models import ConsentLog

    today = date.today()
    person = Participant(email=f"dbtest-born-{stamp()}@example.com", display_name="Без даты",
                         password_hash=PASSWORD_HASH, email_verified_at=now(), is_minor=False,
                         birth_date=None, is_visible=True, public_profile=False)
    db.add(person)
    await db.commit()
    pid = person.id
    current = {"sub": str(pid)}
    try:
        born = date(today.year - 30, 1, 1)
        await update_profile(ProfileUpdate(birth_date=born), current, db)
        rows = list(await db.scalars(select(ConsentLog).where(
            ConsentLog.participant_id == pid, ConsentLog.event_type == "birth_date_set")))
        assert len(rows) == 1 and rows[0].meta["minor"] is False
        # The same date again is not a change and is not logged twice.
        await update_profile(ProfileUpdate(birth_date=born), current, db)
        rows = list(await db.scalars(select(ConsentLog).where(
            ConsentLog.participant_id == pid, ConsentLog.event_type == "birth_date_set")))
        assert len(rows) == 1
    finally:
        await db.rollback()
        await wipe_people([pid])
