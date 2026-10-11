"""Audit-4 F-1: no number of small-field results outweighs one win among 200, and monotonicity holds."""
import random
from datetime import date, timedelta

from hypothesis import given, settings, strategies as st

from app.services.scoring.engine import PER_MONTH_CAP, _result_pool, compute_discipline_score

REF = date(2026, 10, 1)


def _ev(i, place, total, when):
    return dict(id=f"e{i}", place=place, total_participants=total, competition_status="regional",
                team_size=1, event_date=when)


def _farm(k, seed=0):
    rnd = random.Random(seed)
    return [_ev(i, rnd.choice([2, 3, 4, 5]), 6, REF - timedelta(days=rnd.randint(0, 364))) for i in range(k)]


def test_any_volume_of_small_fields_stays_below_one_big_win():
    big = compute_discipline_score([_ev(0, 1, 200, REF - timedelta(days=30))], REF)["lcb"]
    for k in (5, 10, 20, 40, 80):
        assert compute_discipline_score(_farm(k), REF)["lcb"] < big, k


def test_per_month_cap_keeps_the_strongest():
    same_month = [_ev(i, p, 100, date(2026, 9, 1 + i)) for i, p in enumerate([1, 9, 2, 40])]
    pool = _result_pool(same_month, REF)
    assert len(pool) == PER_MONTH_CAP
    assert sorted(e["place"] for _, _, e in pool) == [1, 2]


@settings(max_examples=150, deadline=None)
@given(st.integers(0, 30), st.integers(1, 6), st.integers(2, 300), st.integers(0, 700), st.integers(0, 10**6))
def test_adding_a_small_or_big_field_event_never_lowers_the_score(k, place, total, age, seed):
    base = _farm(k, seed)
    extra = _ev(999, min(place, total), total, REF - timedelta(days=age))
    assert compute_discipline_score(base + [extra], REF)["lcb"] >= compute_discipline_score(base, REF)["lcb"] - 1e-9
