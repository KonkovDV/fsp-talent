"""A public category ranking needs at least BANK_MIN people; four stay hidden, five are shown."""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import delete, func, select

import app.api.v1.public as public
from app.models import CategoryAssignment, GradeConfirmation, Participant
from app.services.identity import give_consent
from app.services.profile import rebuild_profile
from app.services.search.pipeline import BANK_MIN
from tests.integration.conftest import stamp, wipe_people
from tests.integration.test_search_order import _person

ROLE, GRADE = "backend", "lead"


async def _cell(db) -> int:
    return await db.scalar(
        select(func.count()).select_from(GradeConfirmation)
        .join(CategoryAssignment, CategoryAssignment.participant_id == GradeConfirmation.participant_id)
        .where(GradeConfirmation.specialization == ROLE, GradeConfirmation.grade == GRADE,
               CategoryAssignment.primary_role == ROLE, CategoryAssignment.grade == GRADE))


async def _confirmed(db, tag: str, index: int) -> Participant:
    person = await _person(db, tag, index * 5 + 4)            # index*5+4 -> declared grade "lead"
    person.public_profile = True                              # the ranking is a public page (A1b)
    await give_consent(db, "participant", person.id, "pd_distribution")
    db.add(GradeConfirmation(participant_id=person.id, specialization=ROLE, grade=GRADE, p_pass=0.8 + index / 100))
    await db.flush()
    await rebuild_profile(db, person)
    return person


async def test_four_people_stay_hidden_and_five_are_shown(db, monkeypatch):
    async def never_limited(*_a, **_k):
        return False
    monkeypatch.setattr(public, "too_many", never_limited)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={})
    people: list[Participant] = []
    try:
        base = await _cell(db)
        assert base < BANK_MIN - 1, "the test cell must start below the threshold"
        tag = stamp()
        while base + len(people) < BANK_MIN - 1:
            people.append(await _confirmed(db, tag, len(people)))
        assert await _cell(db) == BANK_MIN - 1
        hidden = await public.category_ranking(ROLE, GRADE, request, db)
        assert hidden["total"] == 0 and hidden["items"] == [] and hidden["min_cell"] == BANK_MIN
        people.append(await _confirmed(db, tag, len(people)))
        shown = await public.category_ranking(ROLE, GRADE, request, db)
        assert shown["total"] == BANK_MIN and len(shown["items"]) >= 1
        assert all("participant_id" not in item and "display_name" not in item for item in shown["items"])
    finally:
        await db.rollback()
        ids = [p.id for p in people]
        if ids:
            await db.execute(delete(GradeConfirmation).where(GradeConfirmation.participant_id.in_(ids)))
            await db.commit()
            await wipe_people(ids)
