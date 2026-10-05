"""Grade policy and IRT scoring: the rules the TZ fixes for the test mechanic.

Pure functions only; the DB path is covered by tests/smoke_api.py in CI.
"""
from __future__ import annotations

import collections
from datetime import UTC, datetime, timedelta

import pytest

from app.models.assessment import GRADE_COOLDOWN_DAYS, SESSION_QUESTION_COUNT
from app.seed.questions import QUESTIONS, balanced
from app.services.assessment import (
    MIN_SCORED_QUESTIONS,
    _irt_map,
    decide_grade,
    earned_grade,
    grade_from_theta,
    passed_target,
    posterior_se,
)
from app.services.categorization import assign_category

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def _session(difficulties: list[float], correct: list[bool], a: float = 1.0) -> float:
    return _irt_map([(b, a, c) for b, c in zip(difficulties, correct, strict=True)])


# --- IRT estimate -----------------------------------------------------------------------------

def test_no_responses_returns_prior_mean_not_a_grade_by_itself():
    assert _irt_map([]) == 0.0


def test_theta_is_monotone_in_number_of_correct_answers():
    b = [-0.8, -0.5, 0.0, 0.3, 0.5, 1.0, 1.2, -1.0, 0.4, 1.1]
    thetas = [_session(b, [i < k for i in range(len(b))]) for k in range(len(b) + 1)]
    assert thetas == sorted(thetas)
    assert thetas[0] < -1.0 < 1.0 < thetas[-1]


def test_with_equal_discrimination_only_the_count_of_right_answers_matters():
    # 1PL/2PL with equal a: the raw score is a sufficient statistic, item difficulty does not reweight it.
    easy_right = _session([-1.0, 1.0], [True, False])
    hard_right = _session([-1.0, 1.0], [False, True])
    assert hard_right == pytest.approx(easy_right, abs=1e-6)


def test_right_answer_on_a_more_discriminating_item_counts_more():
    # 2PL: the sufficient statistic is sum(a_i * x_i).
    low_a_right = _irt_map([(0.0, 0.5, True), (0.0, 2.0, False)])
    high_a_right = _irt_map([(0.0, 0.5, False), (0.0, 2.0, True)])
    assert high_a_right > low_a_right


def test_discrimination_parameter_is_used():
    # 2PL: a more discriminating item moves theta further for the same response.
    low = _session([0.0] * 5, [True] * 5, a=0.5)
    high = _session([0.0] * 5, [True] * 5, a=2.0)
    assert high > low > 0


# --- Grade mapping ---------------------------------------------------------------------------

@pytest.mark.parametrize("theta, grade", [
    (-2.0, None), (-1.5, "junior"), (-0.6, "junior"), (-0.5, "middle"),
    (0.49, "middle"), (0.5, "senior"), (1.49, "senior"), (1.5, "lead"), (4.0, "lead"),
])
def test_grade_from_theta_boundaries(theta, grade):
    assert grade_from_theta(theta) == grade


def test_earned_grade_is_capped_one_level_above_target():
    assert earned_grade(3.0, "junior") == "middle"
    assert earned_grade(3.0, "middle") == "senior"
    assert earned_grade(3.0, "lead") == "lead"
    assert earned_grade(-0.6, "middle") == "junior"
    assert earned_grade(-3.0, "junior") is None


def test_earned_grade_does_not_extrapolate_below_the_measured_band():
    # A senior test serves middle/senior/lead items: it cannot vouch for "junior".
    assert earned_grade(-0.6, "senior") is None
    assert earned_grade(0.0, "senior") == "middle"
    assert earned_grade(-1.0, "lead") is None


def test_upgrade_needs_a_margin_of_one_standard_error():
    # "справившийся уверенно": 0.6 clears the senior cut (0.5) only by 0.1, well inside one SE.
    assert earned_grade(0.6, "middle", se=0.5) == "middle"
    assert earned_grade(1.2, "middle", se=0.5) == "senior"
    # Passing the declared grade itself needs no margin.
    assert earned_grade(-0.4, "middle", se=0.5) == "middle"


def test_posterior_se_shrinks_with_more_items():
    one = posterior_se(0.0, [(0.0, 1.0, True)])
    many = posterior_se(0.0, [(0.0, 1.0, True)] * 30)
    assert many < one < 1.0


def test_passed_target():
    assert passed_target("middle", "middle") and passed_target("senior", "middle")
    assert not passed_target("junior", "middle") and not passed_target(None, "junior")


# --- Policy (TZ section 2) -------------------------------------------------------------------

def test_failed_attempt_changes_nothing_and_does_not_lock():
    d = decide_grade("middle", "junior", "senior", NOW)
    assert d.assessed_grade == "middle" and not d.applied and d.locked_until is None
    assert d.reason == "not_passed"
    # No confirmed grade yet: a failed attempt still assigns nothing, so a lower level can be tried.
    d = decide_grade(None, "junior", "middle", NOW)
    assert d.assessed_grade is None and not d.applied and d.locked_until is None


def test_first_confirmation_is_a_baseline_without_cooldown():
    d = decide_grade(None, "middle", "middle", NOW)
    assert d.assessed_grade == "middle" and d.applied and not d.upgraded and d.locked_until is None


def test_upgrade_raises_grade_and_starts_cooldown():
    d = decide_grade("middle", "senior", "senior", NOW)
    assert d.assessed_grade == "senior" and d.applied and d.upgraded
    assert d.locked_until == NOW + timedelta(days=GRADE_COOLDOWN_DAYS)


def test_confident_result_upgrades_one_level_above_target():
    d = decide_grade("middle", earned_grade(2.0, "middle"), "middle", NOW)
    assert d.assessed_grade == "senior" and d.upgraded


def test_test_never_lowers_a_confirmed_grade():
    d = decide_grade("senior", "junior", "junior", NOW)
    assert d.assessed_grade == "senior" and not d.applied and d.reason == "kept_higher_grade"


def test_repeat_of_same_grade_does_not_restart_cooldown():
    d = decide_grade("middle", "middle", "middle", NOW)
    assert not d.applied and d.locked_until is None and d.reason == "confirmed_again"


# --- Exploits that the previous implementation allowed ---------------------------------------

def _bank_difficulties(target: str) -> list[float]:
    order = ["junior", "middle", "senior", "lead"]
    i = order.index(target)
    grades = {order[j] for j in (i - 1, i, i + 1) if 0 <= j < len(order)}
    return [q["difficulty"] for q in QUESTIONS if q["target_grade"] in grades][:SESSION_QUESTION_COUNT]


@pytest.mark.parametrize("target", ["junior", "middle", "senior", "lead"])
def test_submitting_nothing_confirms_no_grade(target):
    """Skipped answers count as wrong. Before the fix an empty submission returned theta=0 -> middle."""
    b = _bank_difficulties(target)
    assert len(b) >= MIN_SCORED_QUESTIONS
    theta = _session(b, [False] * len(b))
    assert not passed_target(earned_grade(theta, target), target)


def test_answering_only_known_items_is_not_rewarded():
    """Before the fix unanswered items were dropped, so 2 right answers out of 15 looked like 2 of 2."""
    b = _bank_difficulties("senior")
    cherry_picked = _session(b, [i < 2 for i in range(len(b))])
    assert not passed_target(earned_grade(cherry_picked, "senior"), "senior")
    assert _session(b[:2], [True, True]) > cherry_picked


# --- Question bank ---------------------------------------------------------------------------

def test_balanced_bank_keeps_content_and_spreads_right_answers():
    bank = [balanced(q, i) for i, q in enumerate(QUESTIONS)]
    for original, shuffled in zip(QUESTIONS, bank, strict=True):
        right = next(o["text"] for o in original["options"] if o["id"] == original["correct_option"])
        assert next(o["text"] for o in shuffled["options"] if o["id"] == shuffled["correct_option"]) == right
        assert sorted(o["text"] for o in shuffled["options"]) == sorted(o["text"] for o in original["options"])
    counts = collections.Counter(q["correct_option"] for q in bank)
    # A constant answer ("b" everywhere) used to score ~55%; now no letter wins more than ~30%.
    assert max(counts.values()) / len(bank) <= 0.30


def test_balancing_is_deterministic():
    assert [balanced(q, i) for i, q in enumerate(QUESTIONS)] == [balanced(q, i) for i, q in enumerate(QUESTIONS)]


# --- Category -------------------------------------------------------------------------------

def test_assessed_grade_outranks_declaration_and_experience():
    cat = assign_category(["Python", "Go"], [], experience_years=10, declared_grade="lead", assessed_grade="middle")
    assert cat["grade"] == "middle" and cat["grade_source"] == "assessed"
    assert "Грейд подтверждён тестом" in cat["explanation"]
    declared = assign_category(["Python", "Go"], [], declared_grade="lead")
    assert declared["grade_source"] == "declared"
    assert any("тестом не подтверждён" in line for line in declared["explanation"])
