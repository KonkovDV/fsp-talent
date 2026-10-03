"""
Unit tests for the scoring engine.

Covers: percentile, event_weight, event_quality, rank_equivalent,
compute_discipline_score, classify_grade, fsp_level_from_rank.
"""
from datetime import date
import math
import pytest
from app.services.scoring.engine import (
    GRADE_LCB_THRESHOLDS,
    PRIOR_MEAN,
    RRF_K,
    classify_grade,
    compute_discipline_score,
    event_quality,
    event_weight,
    fsp_level_from_rank,
    percentile,
    rank_equivalent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REF = date(2026, 10, 1)


def ev(
    place: int,
    total: int = 100,
    status: str = "russia_championship",
    team: int = 1,
    when: date | None = None,
) -> dict:
    return {
        "id": f"{status}-{place}-{total}",
        "place": place,
        "total_participants": total,
        "competition_status": status,
        "team_size": team,
        "event_date": when or REF,
    }


# ---------------------------------------------------------------------------
# percentile
# ---------------------------------------------------------------------------

class TestPercentile:
    def test_first_in_large_field(self):
        assert percentile(1, 100) == pytest.approx(99 / 99)

    def test_last_in_large_field(self):
        assert percentile(100, 100) == pytest.approx(0.0)

    def test_single_participant(self):
        """Single-participant field: mid-point convention = 0.5."""
        assert percentile(1, 1) == pytest.approx(0.5)

    def test_zero_total_safe(self):
        assert 0.0 <= percentile(1, 0) <= 1.0

    def test_monotone_in_place(self):
        """Lower place (better result) => higher percentile."""
        assert percentile(1, 50) > percentile(10, 50) > percentile(50, 50)


# ---------------------------------------------------------------------------
# event_weight
# ---------------------------------------------------------------------------

class TestEventWeight:
    def test_fresh_event_has_max_weight(self):
        w = event_weight(REF, 1, REF)
        assert w == pytest.approx(1.0)

    def test_half_life_is_18_months(self):
        old = date(2025, 4, 1)  # 18 months before REF
        w_old = event_weight(old, 1, REF)
        w_new = event_weight(REF, 1, REF)
        assert w_old == pytest.approx(w_new / 2, rel=0.08)

    def test_team_discount(self):
        solo = event_weight(REF, 1, REF)
        team4 = event_weight(REF, 4, REF)
        assert team4 == pytest.approx(solo / 2, rel=0.01)  # 1/sqrt(4) = 0.5

    def test_future_date_clamped_to_1(self):
        future = date(2027, 1, 1)
        w = event_weight(future, 1, REF)
        assert w == pytest.approx(1.0)  # max(0, negative) => decay=1


# ---------------------------------------------------------------------------
# event_quality
# ---------------------------------------------------------------------------

class TestEventQuality:
    def test_world_is_highest_evsk(self):
        q_world = event_quality(1, 100, "world")
        q_russia = event_quality(1, 100, "russia_championship")
        q_regional = event_quality(1, 100, "regional")
        assert q_world >= q_russia >= q_regional

    def test_quality_capped_at_one(self):
        assert event_quality(1, 100, "world") <= 1.0

    def test_place_monotone(self):
        assert event_quality(1, 100, "russia_championship") > event_quality(10, 100, "russia_championship")


# ---------------------------------------------------------------------------
# rank_equivalent
# ---------------------------------------------------------------------------

class TestRankEquivalent:
    def test_national_first_large_field(self):
        assert rank_equivalent("russia_championship", 1, 100) == "МС"

    def test_national_first_tiny_field(self):
        """Small field -> rank steps down."""
        r = rank_equivalent("russia_championship", 1, 4)
        assert r in ("I", "II", "III")  # not МС or МСМК

    def test_regional_first_big_field(self):
        assert rank_equivalent("regional", 1, 40) == "II"

    def test_other_status_returns_third(self):
        assert rank_equivalent("other", 1, 100) == "III"

    def test_rank_ladder_monotone(self):
        r1 = rank_equivalent("russia_championship", 1, 200)
        r2 = rank_equivalent("russia_championship", 1, 100)
        r3 = rank_equivalent("russia_championship", 1, 20)
        order = ["МСМК", "МС", "I", "II", "III"]
        assert order.index(r1) <= order.index(r2) <= order.index(r3)


# ---------------------------------------------------------------------------
# fsp_level_from_rank
# ---------------------------------------------------------------------------

class TestFspLevelFromRank:
    @pytest.mark.parametrize("rank,expected", [
        ("МСМК", "elite"),
        ("МС", "master"),
        ("I", "candidate_master"),
        ("II", "first_class"),
        ("III", "second_class"),
    ])
    def test_known_ranks(self, rank, expected):
        assert fsp_level_from_rank(rank) == expected

    def test_unknown_rank_returns_none(self):
        assert fsp_level_from_rank("X") is None


# ---------------------------------------------------------------------------
# compute_discipline_score
# ---------------------------------------------------------------------------

class TestComputeDisciplineScore:
    def test_empty_history_returns_prior(self):
        s = compute_discipline_score([])
        assert s["score"] == pytest.approx(PRIOR_MEAN, abs=1e-4)
        assert s["confidence"] == 0.0
        assert s["events_count"] == 0
        assert s["fsp_level"] is None

    def test_better_place_scores_higher(self):
        s1 = compute_discipline_score([ev(1)])
        s40 = compute_discipline_score([ev(40)])
        assert s1["score"] > s40["score"]

    def test_lcb_less_than_score(self):
        """LCB must always be below posterior mean (it's a lower bound)."""
        for place in (1, 10, 50):
            s = compute_discipline_score([ev(place)])
            assert s["lcb"] < s["score"]

    def test_more_events_raises_lcb(self):
        """More evidence => narrower CI => LCB rises toward mean."""
        events_1 = [ev(1)]
        events_5 = [ev(1), ev(2), ev(1), ev(3), ev(1)]
        s1 = compute_discipline_score(events_1, reference_date=REF)
        s5 = compute_discipline_score(events_5, reference_date=REF)
        assert s5["lcb"] > s1["lcb"]

    def test_shrinkage_away_from_extremes(self):
        strong = compute_discipline_score([ev(1, 200, "world")])
        weak = compute_discipline_score([ev(80, 80, "other")])
        assert 0.30 < strong["score"] < 0.95
        assert 0.0 < weak["score"] < 0.30

    def test_team_widens_uncertainty(self):
        solo = compute_discipline_score([ev(1, team=1)])
        team = compute_discipline_score([ev(1, team=4)])
        assert team["sigma"] > solo["sigma"]
        assert team["lcb"] < solo["lcb"]

    def test_half_life_decay(self):
        fresh = compute_discipline_score([ev(1, when=REF)], reference_date=REF)
        stale = compute_discipline_score([ev(1, when=date(2022, 1, 1))], reference_date=REF)
        assert fresh["score"] > stale["score"]

    def test_fsp_level_assigned(self):
        s = compute_discipline_score([ev(1, 100, "russia_championship")])
        assert s["fsp_level"] is not None

    def test_top_event_ids_captured(self):
        events = [ev(1), ev(2), ev(3), ev(4), ev(5)]
        s = compute_discipline_score(events)
        assert len(s["top_event_ids"]) <= 3  # TOP_N

    def test_wrong_date_type_raises(self):
        with pytest.raises(TypeError):
            compute_discipline_score([{
                "id": "x", "place": 1, "total_participants": 10,
                "competition_status": "regional", "team_size": 1,
                "event_date": "2026-01-01",  # str instead of date
            }])


# ---------------------------------------------------------------------------
# classify_grade
# ---------------------------------------------------------------------------

class TestClassifyGrade:
    def test_all_thresholds(self):
        assert classify_grade(0.90) == "lead"
        assert classify_grade(0.85) == "lead"   # exact boundary
        assert classify_grade(0.84) == "senior"
        assert classify_grade(0.65) == "senior"  # exact boundary
        assert classify_grade(0.64) == "middle"
        assert classify_grade(0.40) == "middle"  # exact boundary
        assert classify_grade(0.39) == "junior"
        assert classify_grade(0.00) == "junior"
        assert classify_grade(-0.1) == "junior"  # below-zero LCB is valid

    def test_threshold_dict_keys_cover_all_grades(self):
        assert set(GRADE_LCB_THRESHOLDS.keys()) == {"lead", "senior", "middle", "junior"}

    def test_monotone(self):
        order = ["junior", "middle", "senior", "lead"]
        grades = [classify_grade(lcb) for lcb in (0.1, 0.5, 0.7, 0.9)]
        for i in range(len(grades) - 1):
            assert order.index(grades[i]) <= order.index(grades[i + 1])
