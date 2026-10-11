"""SD-08 (152-ФЗ ст. 9): a person who signed up as 15–17 cannot become an adult by entering a first birth date."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.api.errors import ApiError
from app.api.v1.candidates import ProfileUpdate, update_profile
from app.models import Participant
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def _person(db, is_minor: bool, created_at: datetime | None = None) -> Participant:
    person = Participant(email=f"dbtest-age-{stamp()}@example.com", display_name="Возраст",
                         password_hash=PASSWORD_HASH, email_verified_at=now(), is_minor=is_minor,
                         birth_date=None, is_visible=True, public_profile=False, minor_consent_given=False,
                         created_at=created_at or now())
    db.add(person)
    await db.commit()
    return person


async def test_a_minor_signup_rejects_an_adult_first_birth_date(db):
    person = await _person(db, is_minor=True)
    pid = person.id
    try:
        with pytest.raises(ApiError) as err:
            await update_profile(ProfileUpdate(birth_date=date(1990, 1, 1)), {"sub": str(pid)}, db)
        assert err.value.status_code == 422 and err.value.code == "age_mismatch"
        await db.rollback()
        fresh = await db.get(Participant, pid)
        await db.refresh(fresh)
        assert fresh.birth_date is None and fresh.is_minor and not fresh.discoverable
    finally:
        await db.rollback()
        await wipe_people([pid])


async def test_a_minor_signup_keeps_a_minor_birth_date(db):
    today = date.today()
    person = await _person(db, is_minor=True)
    pid = person.id
    try:
        await update_profile(ProfileUpdate(birth_date=date(today.year - 16, 1, 1)), {"sub": str(pid)}, db)
        fresh = await db.get(Participant, pid)
        assert fresh.is_minor and not fresh.discoverable   # still waits for the guardian's consent
    finally:
        await db.rollback()
        await wipe_people([pid])


async def test_a_minor_who_turned_18_since_signup_enters_the_real_date(db):
    today = date.today()
    signed_up = datetime(today.year - 2, 1, 15, tzinfo=UTC)
    person = await _person(db, is_minor=True, created_at=signed_up)
    pid = person.id
    try:
        # 17 on the signup day, 19 now.
        await update_profile(ProfileUpdate(birth_date=date(today.year - 19, 6, 1)), {"sub": str(pid)}, db)
        fresh = await db.get(Participant, pid)
        assert fresh.is_minor is False
    finally:
        await db.rollback()
        await wipe_people([pid])


async def test_an_adult_signup_enters_an_adult_date(db):
    person = await _person(db, is_minor=False)
    pid = person.id
    try:
        await update_profile(ProfileUpdate(birth_date=date(1990, 1, 1)), {"sub": str(pid)}, db)
        fresh = await db.get(Participant, pid)
        assert fresh.birth_date == date(1990, 1, 1) and fresh.is_minor is False
    finally:
        await db.rollback()
        await wipe_people([pid])
