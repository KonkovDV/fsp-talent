"""Audit-5 A1b: the public ranking counts only public adults; a minor with a guardian's consent never appears."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from sqlalchemy import delete

import app.api.v1.public as public
from app.models import GradeConfirmation, Participant
from app.services.identity import give_consent
from app.services.profile import rebuild_profile
from app.services.search.pipeline import BANK_MIN
from tests.integration.conftest import stamp, wipe_people
from tests.integration.test_search_order import _person

ROLE, GRADE = "backend", "lead"


async def _confirmed(db, tag: str, index: int, *, minor: bool = False) -> Participant:
    person = await _person(db, tag, index * 5 + 4)
    if minor:
        today = date.today()
        person.birth_date = date(today.year - 16, 1, 1)
        person.is_minor = True
        person.minor_consent_given = True          # visible to employers inside the product
    person.public_profile = True
    await give_consent(db, "participant", person.id, "pd_distribution")
    db.add(GradeConfirmation(participant_id=person.id, specialization=ROLE, grade=GRADE, p_pass=0.99 if minor else 0.8))
    await db.flush()
    await rebuild_profile(db, person)
    return person


async def test_a_consenting_minor_is_neither_listed_nor_counted(db, monkeypatch):
    async def never_limited(*_a, **_k):
        return False
    monkeypatch.setattr(public, "too_many", never_limited)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={})
    tag = stamp()
    people: list[Participant] = []
    try:
        base = (await public.category_ranking(ROLE, GRADE, request, db))["total"]
        assert base == 0, "the test cell must start hidden"
        minor = await _confirmed(db, tag, 0, minor=True)
        people.append(minor)
        while len(people) < BANK_MIN:
            people.append(await _confirmed(db, tag, len(people)))
        # Four public adults and one minor: still under k over the public set, so nothing is shown.
        page = await public.category_ranking(ROLE, GRADE, request, db)
        assert page["total"] == 0 and page["items"] == []
        people.append(await _confirmed(db, tag, len(people)))
        page = await public.category_ranking(ROLE, GRADE, request, db)
        assert page["total"] == BANK_MIN                     # five adults, the minor is not counted
        assert all(round(item.get("test", 0), 2) != 0.99 for item in page["items"])
    finally:
        await db.rollback()
        ids = [p.id for p in people]
        await db.execute(delete(GradeConfirmation).where(GradeConfirmation.participant_id.in_(ids)))
        await db.commit()
        await wipe_people(ids)
