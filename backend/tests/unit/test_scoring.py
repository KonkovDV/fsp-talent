from datetime import date

import pytest

from app.services.scoring.engine import (
    compute_discipline_score,
    event_quality,
    event_weight,
    months_between,
    percentile,
    rank_at_least,
    rank_equivalent,
)


def ev(place, total=100, status="russia_championship", team=1, when=None):
    return {"id": f"{status}-{place}", "place": place, "total_participants": total,
            "competition_status": status, "team_size": team, "event_date": when or date.today()}


# ---------------------------------------------------------------------------
# Existing tests (unchanged)
# ---------------------------------------------------------------------------

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
# New: rank_at_least
# ---------------------------------------------------------------------------

def test_rank_at_least_ordering():
    """Функция rank_at_least(rank, minimum) возвращает True, когда rank георганически не хуже minimum."""
    # МС — сильнейший ранг (индекс 0 в RANK_ORDER) — бьёт всех
    assert rank_at_least("МС", "МС")
    assert rank_at_least("МС", "КМС")
    assert rank_at_least("МС", "I")
    assert rank_at_least("МС", "юн")
    # КМС не бьёт МС
    assert rank_at_least("КМС", "КМС")
    assert rank_at_least("КМС", "I")
    assert not rank_at_least("КМС", "МС")
    # I сильнее II/III/юн, слабее МС/КМС
    assert rank_at_least("I", "I")
    assert not rank_at_least("I", "КМС")
    # юн — слабейший именованный ранг
    assert rank_at_least("юн", "юн")
    assert not rank_at_least("юн", "III")
    # None — безранговый результат, не удовлетворяет никакому minimum
    assert not rank_at_least(None, "юн")
    assert not rank_at_least(None, "МС")


# ---------------------------------------------------------------------------
# New: months_between
# ---------------------------------------------------------------------------

def test_months_between_non_negative_and_monotone():
    """Функция months_between должна возвращать 0 для той же даты и будущих событий."""
    ref = date(2026, 10, 1)
    assert months_between(ref, ref) == pytest.approx(0.0)
    # Будущее событие: кламп в 0
    assert months_between(date(2027, 1, 1), ref) == pytest.approx(0.0)
    # ~18 месяцев назад ≈ полпериод затухания
    roughly_18m = months_between(date(2025, 4, 1), ref)
    assert 17.0 < roughly_18m < 19.0
    # Монотонность
    one_year = months_between(date(2025, 10, 1), ref)
    two_years = months_between(date(2024, 10, 1), ref)
    assert one_year == pytest.approx(12.0, rel=0.05)
    assert two_years > one_year


# ---------------------------------------------------------------------------
# New: rank_equivalent -- full EVSK_LADDER branch coverage
# ---------------------------------------------------------------------------

def test_rank_equivalent_world():
    assert rank_equivalent("world", 1, 100) == "МС"
    assert rank_equivalent("world", 8, 100) == "МС"
    assert rank_equivalent("world", 9, 100) == "КМС"
    assert rank_equivalent("world", 16, 100) == "КМС"
    assert rank_equivalent("world", 17, 100) == "I"
    assert rank_equivalent("world", 32, 100) == "I"
    # За порогом последнего порога → None
    assert rank_equivalent("world", 33, 100) is None
    # Малая выборка: МС/КМС требуют не менее 6 участников
    assert rank_equivalent("world", 1, 5) == "I"   # понижено с МС
    assert rank_equivalent("world", 9, 5) == "I"   # понижено с КМС


def test_rank_equivalent_russia_cup():
    assert rank_equivalent("russia_cup", 1, 50) == "МС"
    assert rank_equivalent("russia_cup", 2, 50) == "КМС"
    assert rank_equivalent("russia_cup", 4, 50) == "КМС"
    assert rank_equivalent("russia_cup", 9, 50) == "I"
    assert rank_equivalent("russia_cup", 17, 50) == "II"
    assert rank_equivalent("russia_cup", 33, 50) == "III"
    assert rank_equivalent("russia_cup", 34, 50) is None


def test_rank_equivalent_all_russian_and_youth():
    # all_russian и russia_youth с одинаковыми порогами
    for status in ("all_russian", "russia_youth"):
        assert rank_equivalent(status, 1, 30) == "КМС"
        assert rank_equivalent(status, 4, 30) == "I"
        assert rank_equivalent(status, 9, 30) == "II"
        assert rank_equivalent(status, 17, 30) == "III"
        assert rank_equivalent(status, 33, 30) is None


def test_rank_equivalent_federal_district():
    assert rank_equivalent("federal_district", 1, 30) == "I"
    assert rank_equivalent("federal_district", 3, 30) == "I"
    assert rank_equivalent("federal_district", 4, 30) == "II"
    assert rank_equivalent("federal_district", 8, 30) == "II"
    assert rank_equivalent("federal_district", 9, 30) == "III"
    assert rank_equivalent("federal_district", 16, 30) == "III"
    assert rank_equivalent("federal_district", 17, 30) is None


def test_rank_equivalent_other():
    assert rank_equivalent("other", 1, 10) == "III"
    assert rank_equivalent("other", 3, 10) == "III"
    assert rank_equivalent("other", 4, 10) == "юн"
    assert rank_equivalent("other", 8, 10) == "юн"
    assert rank_equivalent("other", 9, 10) is None
    # Неизвестный статус → пороги как у "other"
    assert rank_equivalent("unknown_status", 1, 10) == "III"


# ---------------------------------------------------------------------------
# New: DisciplineResult fields -- best_rank and top_event_ids
# ---------------------------------------------------------------------------

def test_best_rank_picks_strongest_across_events():
    """Поле best_rank выбирает минимальный индекс в RANK_ORDER (сильнейший ранг) по всем событиям."""
    ref = date(2026, 10, 1)
    events = [
        ev(1, 100, "russia_championship", when=ref),               # МС
        {**ev(5, 100, "regional", when=ref), "id": "reg-5"},       # III
        {**ev(2, 100, "federal_district", when=ref), "id": "fd-2"}, # II
    ]
    result = compute_discipline_score(events, reference_date=ref)
    assert result["best_rank"] == "МС"
    assert result["events_count"] == 3
    assert result["team_events_count"] == 0


def test_best_rank_is_none_when_all_places_are_below_thresholds():
    # place=9 в "other" — за порогом 8 (юн), возвращает None
    result = compute_discipline_score([ev(9, 10, "other")])
    assert result["best_rank"] is None


def test_top_event_ids_returns_at_most_three_by_descending_quality_weight():
    """Поле top_event_ids: не более 3, отсортированы по q*w по убыванию."""
    ref = date(2026, 10, 1)
    events = [
        {**ev(1, 100, "russia_championship", when=ref), "id": "A"},
        {**ev(2, 100, "russia_championship", when=ref), "id": "B"},
        {**ev(3, 100, "russia_championship", when=ref), "id": "C"},
        {**ev(4, 100, "russia_championship", when=ref), "id": "D"},
    ]
    result = compute_discipline_score(events, reference_date=ref)
    assert result["top_event_ids"] == ["A", "B", "C"]
    assert len(result["top_event_ids"]) == 3


def test_top_event_ids_with_fewer_than_three_events():
    ref = date(2026, 10, 1)
    result = compute_discipline_score(
        [ev(1, 100, "russia_championship", when=ref)], reference_date=ref)
    assert len(result["top_event_ids"]) == 1
    assert result["top_event_ids"][0] == "russia_championship-1"


# ---------------------------------------------------------------------------
# New: scoring_version пробрасывается в результат
# ---------------------------------------------------------------------------

def test_scoring_version_is_present():
    from app.services.scoring.engine import VERSION
    result = compute_discipline_score([])
    assert result["scoring_version"] == VERSION
    assert result["scoring_version"].startswith("v")
