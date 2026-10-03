from datetime import date
import pytest
from app.services.scoring.engine import (
    compute_discipline_score, event_quality, event_weight, percentile, rank_equivalent,
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
