import random
from datetime import date, timedelta

import pytest

from app.services.scoring.engine import (
    EVENT_CAP,
    best_subset_exact,
    best_subset_greedy,
    compute_discipline_score,
    event_quality,
    event_weight,
    lcb_star,
    months_between,
    percentile,
    rank_at_least,
    result_class,
)
from app.validation.fsp_axis import history


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
    strong = compute_discipline_score([ev(1, 200, "regional")])
    weak = compute_discipline_score([ev(80, 80, "other")])
    assert 0.30 < strong["score"] < 0.95
    # A plain participation is not evidence (v4): the score stays at the prior, it is not pulled under it.
    assert weak["score"] == pytest.approx(0.30, abs=1e-4)


def test_empty_history_is_the_prior():
    score = compute_discipline_score([])
    assert score["score"] == pytest.approx(0.30, abs=1e-4)
    assert score["confidence"] == 0
    assert score["events_count"] == 0


# ---------------------------------------------------------------------------
# v3.1.0: participation scores 0 and only the strongest events enter the sum (Q&A with ФСП)
# ---------------------------------------------------------------------------

STATUSES = ["world", "russia_championship", "russia_cup", "russia_youth", "all_russian",
            "federal_district", "regional", "other"]


def test_competition_status_does_not_change_the_quality():
    for place, total in [(1, 100), (2, 100), (3, 40), (7, 100), (30, 100), (90, 100), (1, 3)]:
        values = {event_quality(place, total, status) for status in STATUSES}
        assert len(values) == 1, (place, total, values)
    ref = date(2026, 10, 1)
    scores = {status: compute_discipline_score([ev(2, 50, status, when=ref)], reference_date=ref)["lcb"]
              for status in STATUSES}
    assert len(set(scores.values())) == 1, scores


def test_winner_beats_prize_beats_top_beats_participant():
    classes = [result_class(p, 100) for p in (1, 2, 3, 10, 50, 51, 100)]
    assert classes == ["winner", "prize", "prize", "top10", "top50", "participant", "participant"]
    qualities = [event_quality(p, 100) for p in (1, 2, 10, 50, 100)]
    assert qualities == sorted(qualities, reverse=True) and len(set(qualities)) == 5


def test_small_field_gives_no_prize_class():
    assert result_class(1, 3) == "top50"      # a win among three is not a real win
    assert result_class(1, 1) == "participant"
    assert result_class(2, 6) == "prize" and result_class(1, 6) == "winner"


def test_many_participations_do_not_beat_a_few_wins():
    ref = date(2026, 10, 1)
    padded = [{**ev(80, 100, "other", when=ref), "id": f"p{i}"} for i in range(20)]
    wins = [{**ev(1, 100, "other", when=ref), "id": f"w{i}"} for i in range(2)]
    many = compute_discipline_score(padded, reference_date=ref)
    few = compute_discipline_score(wins, reference_date=ref)
    assert few["lcb"] > many["lcb"] and few["score"] > many["score"]
    # Participation alone is the empty history: it neither lifts nor lowers the bound (audit 2026-10, H-3).
    empty = compute_discipline_score([], reference_date=ref)
    assert many["lcb"] == empty["lcb"] and many["score"] == empty["score"]
    # A participation added to wins changes nothing: it is not evidence of skill and not a penalty.
    mixed = compute_discipline_score(wins + padded[:1], reference_date=ref)
    assert mixed["lcb"] == few["lcb"] and mixed["score"] == few["score"]


def test_participation_scores_nothing_and_the_cap_drops_the_weakest():
    assert event_quality(90, 100) == 0.0
    ref = date(2026, 10, 1)
    kept = [{**ev(1, 100, "other", when=ref), "id": f"w{i}"} for i in range(EVENT_CAP)]
    extra = [*kept, {**ev(90, 100, "other", when=ref), "id": "pad"}]
    assert compute_discipline_score(kept, reference_date=ref)["lcb"] == (
        compute_discipline_score(extra, reference_date=ref)["lcb"])
    assert compute_discipline_score(extra, reference_date=ref)["events_count"] == EVENT_CAP + 1


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
    assert rank_at_least("МС", "III юн.")
    # КМС не бьёт МС
    assert rank_at_least("КМС", "КМС")
    assert rank_at_least("КМС", "I")
    assert not rank_at_least("КМС", "МС")
    # I сильнее II/III и юношеских, слабее МС/КМС
    assert rank_at_least("I", "I")
    assert not rank_at_least("I", "КМС")
    # III юн. — слабейший именованный ранг
    assert rank_at_least("III юн.", "III юн.")
    assert not rank_at_least("III юн.", "III")
    # None — без разряда, не удовлетворяет никакому minimum
    assert not rank_at_least(None, "III юн.")
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


def test_the_score_does_not_carry_a_rank():
    result = compute_discipline_score([ev(1, 100, "russia_championship")])
    assert "best_rank" not in result


def test_top_event_ids_returns_at_most_three_by_descending_quality_weight():
    """Поле top_event_ids: не более 3, отсортированы по q*w по убыванию."""
    ref = date(2026, 10, 1)
    events = [
        {**ev(1, 100, "russia_championship", when=ref - timedelta(days=0)), "id": "A"},
        {**ev(2, 100, "russia_championship", when=ref - timedelta(days=31)), "id": "B"},
        {**ev(3, 100, "russia_championship", when=ref - timedelta(days=62)), "id": "C"},
        {**ev(4, 100, "russia_championship", when=ref - timedelta(days=93)), "id": "D"},
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

def test_adding_event_never_lowers_lcb():
    rng = random.Random(101)
    ref = date(2026, 10, 1)
    for i in range(2000):
        events = history(rng, rng.gauss(0.0, 1.0))
        before = lcb_star(events, reference_date=ref)["lcb"]
        extra = {
            "id": f"extra-{i}",
            "place": rng.randint(1, 80),
            "total_participants": rng.choice((6, 16, 50, 100)),
            "competition_status": "other",
            "team_size": rng.randint(1, 5),
            "event_date": ref - timedelta(days=rng.randrange(0, 49) * 30),
        }
        after = lcb_star([*events, extra], reference_date=ref)["lcb"]
        assert after >= before - 1e-9


def test_greedy_subset_matches_the_exhaustive_search_up_to_twelve_events():
    from app.services.scoring.engine import _lcb

    rng = random.Random(102)
    ref = date(2026, 10, 1)
    for _ in range(40):
        events = history(rng, rng.gauss(0.0, 1.0))[:12]
        weighted = []
        for e in events:
            q = event_quality(e["place"], e["total_participants"])
            w = event_weight(e["event_date"], e["team_size"], ref)
            weighted.append((q, w, e))
        assert _lcb(best_subset_greedy(weighted)) == pytest.approx(_lcb(best_subset_exact(weighted)), abs=1e-9)
    for n in range(13):
        weighted = [(rng.random(), 0.2 + rng.random(), {"id": str(i)}) for i in range(n)]
        assert _lcb(best_subset_greedy(weighted)) == pytest.approx(_lcb(best_subset_exact(weighted)), abs=1e-9)


def test_scoring_version_is_present():
    from app.services.scoring.engine import VERSION
    result = compute_discipline_score([])
    assert result["scoring_version"] == VERSION
    assert result["scoring_version"].startswith("v")
