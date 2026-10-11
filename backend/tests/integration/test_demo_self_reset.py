"""DoR-04: a juror on the demo stand starts over without touching anybody else."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.api.errors import ApiError
from app.api.v1 import candidates as api
from app.models import Participant, Skill
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def _person(db, email: str) -> tuple[Participant, bool]:
    found = await db.scalar(select(Participant).where(Participant.email == email))
    if found is not None:
        return found, False
    person = Participant(email=email, display_name="Жюри", password_hash=PASSWORD_HASH,
                         email_verified_at=now(), is_minor=False, is_visible=True, public_profile=False,
                         region="Москва")
    db.add(person)
    await db.flush()
    return person, True


async def _dirty(db, person: Participant) -> None:
    person.specialization, person.declared_grade, person.survey_at = "backend", "junior", now()
    person.grade_locked_until = now() + timedelta(days=30)
    db.add(Skill(participant_id=person.id, name="Python", raw_name="Python",
                 trust_level="self_reported", confirmed=False))
    await db.flush()


async def _skills(db, person) -> int:
    return await db.scalar(select(func.count()).select_from(Skill).where(Skill.participant_id == person.id))


async def test_a_juror_resets_only_himself(db, monkeypatch):
    monkeypatch.setattr(api.settings, "DEMO_MODE", True)
    jury3, new3 = await _person(db, "jury3@demo.talent")
    jury4, new4 = await _person(db, "jury4@demo.talent")
    created = [p.id for p, new in ((jury3, new3), (jury4, new4)) if new]
    try:
        await _dirty(db, jury3)
        await _dirty(db, jury4)
        hash_before = jury3.password_hash
        jury3.birth_date = None  # a stand seeded before 887401f
        await db.commit()
        for _ in range(2):  # idempotent
            assert await api.reset_my_demo({"sub": str(jury3.id)}, db) == {"reset": True}
        await db.refresh(jury3)
        await db.refresh(jury4)
        assert jury3.survey_at is None and jury3.grade_locked_until is None and jury3.specialization is None
        assert await _skills(db, jury3) == 0
        assert jury3.password_hash == hash_before
        from app.services.demo_reset import JURY_BIRTH
        assert jury3.birth_date == JURY_BIRTH and jury3.is_minor is False
        assert jury4.grade_locked_until is not None and await _skills(db, jury4) >= 1
    finally:
        await wipe_people(created)


@pytest.mark.parametrize("demo,prefix", [(True, "fsp001-like"), (False, "jury")])
async def test_others_and_production_get_403(db, monkeypatch, demo, prefix):
    monkeypatch.setattr(api.settings, "DEMO_MODE", demo)
    email = "jury5@demo.talent" if prefix == "jury" else f"dbtest-demo-{stamp()}@example.com"
    person, new = await _person(db, email)
    await db.commit()
    try:
        with pytest.raises(ApiError) as caught:
            await api.reset_my_demo({"sub": str(person.id)}, db)
        assert caught.value.status_code == 403 and caught.value.code == "demo_reset_forbidden"
    finally:
        if new:
            await wipe_people([person.id])
