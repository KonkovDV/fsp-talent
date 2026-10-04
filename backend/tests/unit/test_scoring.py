from datetime import date

import pytest

from app.services.scoring.engine import (
    compute_discipline_score,
    event_quality,
    event_weight,
    grade_from_lcb,
    percentile,
    rank_equivalent,
)


def ev(place, total=100, status="russia_championship", team=1, when=None):
    return {"id": f"{status}-{place}", "place": place, "total_participants": total,
            "competition_status": status, "team_size": team, "event_date": when or date.today()}


def test_better_place_scores_higher():
    assert compute_discipline_score([ev(1)])["score"] > compute_discipline_score([ev(40)])["score"]


def test_single_participant_is_defined():
    score = compute_discipline_score([ev(1, 1, "regional")])
    assert score["events_count"] == 1
    assert 0 < score["score"] < 1
    assert percentile(1, 1) == pytest.approx(0.5)


def test_team_widens_uncertainty_instead_of_changing_the_result():
    solo = compute_discipline_score([ev(1, team=1)])
    team = compute_discipline_score([ev(1, team=4)])
    assert event_quality(1, 100, "russia_championship") == event_quality(1, 100, "russia_championship")
    assert team["sigma"] > solo["sigma"]
    assert team["confidence"] < solo["confidence"]


def test_shrinkage_keeps_one_event_away_from_the_extremes():
    strong = compute_discipline_score([ev(1, 200, "world")])
    weak = compute_discipline_score([ev(80, 80, "other")])
    assert 0.30 < strong["score"] < 0.95
    assert 0 < weak["score"] < 0.30


def test_empty_history_is_the_prior():
    score = compute_discipline_score([])
    assert score["score"] == pytest.approx(0.30, abs=1e-4)
    assert score["confidence"] == 0
    assert score["events_count"] == 0


def test_rank_ladder_and_small_field_downgrade():
    assert rank_equivalent("russia_championship", 1, 100) == "МС"
    assert rank_equivalent("russia_championship", 1, 4) == "I"
    assert rank_equivalent("regional", 1, 40) == "II"
    assert event_quality(1, 100, "russia_championship") > event_quality(1, 100, "regional")


def test_more_equal_evidence_raises_the_lower_bound():
    ref = date(2026, 10, 1)
    one = compute_discipline_score([ev(1, when=ref)], reference_date=ref)
    two = compute_discipline_score(
        [ev(1, when=ref), {**ev(1, when=ref), "id": "same-quality"}], reference_date=ref)
    assert two["sigma"] < one["sigma"]
    assert two["confidence"] > one["confidence"]
    assert two["lcb"] > one["lcb"]
    assert two["score"] > one["score"]


def test_half_life_is_eighteen_months():
    ref = date(2026, 10, 1)
    fresh = event_weight(ref, 1, ref)
    old = event_weight(date(2025, 4, 1), 1, ref)
    assert old == pytest.approx(fresh / 2, rel=0.08)
    recent = compute_discipline_score([ev(1, when=ref)], reference_date=ref)
    stale = compute_discipline_score([ev(1, when=date(2022, 1, 1))], reference_date=ref)
    assert recent["score"] > stale["score"]


# ---------------------------------------------------------------------------
# grade_from_lcb: calibration tests
# ---------------------------------------------------------------------------

def test_grade_from_lcb_empty_history_is_not_informative():
    """LCB of empty history (~0.16) must return None -- prior only, no evidence."""
    empty = compute_discipline_score([])
    assert grade_from_lcb(empty["lcb"]) is None


def test_grade_from_lcb_single_regional_win_gives_junior():
    """A single regional win (place 1, N=50) -> LCB ~0.27 -> 'junior'."""
    ref = date(2026, 10, 1)
    score = compute_discipline_score([ev(1, 50, "regional", when=ref)], reference_date=ref)
    assert score["lcb"] >= 0.25
    assert grade_from_lcb(score["lcb"]) == "junior"


def test_grade_from_lcb_champion_gives_senior():
    """Multiple top national results -> LCB >= 0.60 -> 'senior'."""
    ref = date(2026, 10, 1)
    events = [
        ev(1, 200, "russia_championship", when=ref),
        ev(2, 180, "russia_championship", when=date(2026, 3, 1)),
        ev(1, 150, "all_russian", when=date(2025, 11, 1)),
    ]
    score = compute_discipline_score(events, reference_date=ref)
    assert score["lcb"] >= 0.60
    assert grade_from_lcb(score["lcb"]) == "senior"


def test_grade_from_lcb_thresholds_are_monotone():
    """grade_from_lcb must be non-decreasing with LCB."""
    grades = ["junior", "middle", "senior"]
    lcbs = [0.25, 0.40, 0.60]
    for lcb, expected in zip(lcbs, grades):
        assert grade_from_lcb(lcb) == expected
    # Values just below each threshold return the lower grade or None
    assert grade_from_lcb(0.249) is None
    assert grade_from_lcb(0.399) == "junior"
    assert grade_from_lcb(0.599) == "middle"


def test_grade_from_lcb_does_not_produce_lead():
    """'lead' is never returned by grade_from_lcb -- it requires organisational context."""
    assert grade_from_lcb(0.999) == "senior"
