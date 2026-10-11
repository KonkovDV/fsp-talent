"""Audit 2026-10 H-3 / audit-2 P0-2: the FSP axis is monotone in the evidence (hypothesis).

v3 took the five strongest events by q·w including zeros; 48 % of random additions lowered the bound
and 37.5 % of random histories sat under the empty history (audit-2). v4 scores only result events
(q > 0) and takes the best subset, so adding any event never lowers the bound and nothing is below LCB0.
"""
from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.scoring.engine import EXACT_SUBSET_LIMIT, LCB0, VERSION, compute_discipline_score

REF = date(2026, 10, 1)


@st.composite
def event(draw, idx=st.integers(0, 10**9)):
    total = draw(st.integers(1, 300))
    return {
        "id": f"e{draw(idx)}",
        "place": draw(st.integers(1, total)),
        "total_participants": total,
        "competition_status": draw(st.sampled_from(("regional", "russia_championship", "other"))),
        "team_size": draw(st.integers(1, 6)),
        "event_date": REF - timedelta(days=draw(st.integers(0, 3650))),
    }


def _positive(events):
    from app.services.scoring.engine import event_quality
    return sum(1 for e in events if event_quality(e["place"], e["total_participants"]) > 0)


@settings(max_examples=3000, deadline=None, derandomize=True)
@given(st.lists(event(), max_size=12), event())
def test_adding_any_event_never_lowers_the_bound(events, extra):
    if _positive([*events, extra]) > EXACT_SUBSET_LIMIT:
        return
    before = compute_discipline_score(events, REF)["lcb"]
    after = compute_discipline_score([*events, extra], REF)["lcb"]
    assert after + 1e-9 >= before


@settings(max_examples=2000, deadline=None, derandomize=True)
@given(st.lists(event(), max_size=20))
def test_no_history_is_ever_below_the_empty_history(events):
    assert compute_discipline_score(events, REF)["lcb"] + 1e-9 >= round(LCB0, 4)


@settings(max_examples=1500, deadline=None, derandomize=True)
@given(st.lists(event(), max_size=10), event(), st.integers(1, 300))
def test_a_better_place_never_lowers_the_bound(events, e, better):
    worse = dict(e)
    improved = dict(e, place=max(1, min(e["place"], better)))
    a = compute_discipline_score([*events, worse], REF)["lcb"]
    b = compute_discipline_score([*events, improved], REF)["lcb"]
    assert b + 1e-9 >= a


def test_participations_are_counted_but_never_scored():
    plain = [{"id": f"p{i}", "place": 90, "total_participants": 100, "competition_status": "other",
              "team_size": 1, "event_date": REF} for i in range(40)]
    result = compute_discipline_score(plain, REF)
    assert result["events_count"] == 40 and result["top_event_ids"] == []
    assert result["lcb"] == round(LCB0, 4)
    assert VERSION == "v4.1.0"
