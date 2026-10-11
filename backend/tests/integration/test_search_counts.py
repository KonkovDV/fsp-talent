"""The search header explains its count; the card path reports the held-back people too."""
from __future__ import annotations

from app.services.search.pipeline import BANK_MIN, search_candidates
from tests.integration.conftest import stamp, wipe_people
from tests.integration.test_search_order import _person


async def test_a_stricter_filter_says_how_many_sit_in_the_pair(db):
    tag = stamp()
    people = [await _person(db, tag, i) for i in range(10)]   # backend, grades cycle intern..lead
    ids = [p.id for p in people]
    try:
        await db.commit()
        role_only = await search_candidates(db, role="backend", limit=200)
        pair = await search_candidates(db, role="backend", grade="middle", limit=200)
        exact = await search_candidates(db, role="backend", grade="middle", grade_span="exact", limit=200)
        assert "platform_held" in pair and "in_category" in pair
        assert role_only["in_category"] is None
        # The near span may list more than the role alone; the exact pair never does.
        assert exact["total"] <= role_only["total"]
        if pair["in_category_hidden"]:
            # k-anonymity: a cell of 1–4 people is not printed as a number (BANK_MIN).
            assert pair["in_category"] is None and 0 < exact["total"] < BANK_MIN
        else:
            assert pair["in_category"] == exact["total"]
            assert pair["in_category"] <= pair["total"]
            assert pair["in_category"] >= 2                     # our two middles
    finally:
        await db.rollback()
        await wipe_people(ids)


async def test_a_small_cell_count_is_hidden(db):
    tag = stamp()
    people = [await _person(db, tag, i) for i in range(5)]    # one person per grade
    ids = [p.id for p in people]
    try:
        await db.commit()
        exact = await search_candidates(db, role="backend", grade="lead", grade_span="exact", limit=200)
        pair = await search_candidates(db, role="backend", grade="lead", limit=200)
        if exact["total"] < BANK_MIN:
            assert pair["in_category"] is None and pair["in_category_hidden"] is True
    finally:
        await db.rollback()
        await wipe_people(ids)
