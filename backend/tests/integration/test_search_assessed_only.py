"""ST-09: «Только грейд, подтверждённый тестом» returned ~80 % cards marked «не подтверждён»."""
from __future__ import annotations

from app.services.search.pipeline import search_candidates
from tests.integration.conftest import stamp, wipe_people
from tests.integration.test_search_order import _person


async def test_the_assessed_filter_lists_only_cards_confirmed_by_the_test(db):
    tag = stamp()
    people = [await _person(db, tag, i) for i in range(4)]
    ids = [p.id for p in people]
    try:
        # A test on record (Participant.assessed_grade), but the backend category is still the declared one.
        for person in people:
            person.assessed_grade = "middle"
        await db.commit()
        out = await search_candidates(db, role="backend", assessed_only=True, limit=200)
        assert all(card["grade_source"] == "assessed" for card in out["items"])
        listed = {card["candidate_id"] for card in out["items"]}
        assert not listed & {str(i) for i in ids}
    finally:
        await db.rollback()
        await wipe_people(ids)
