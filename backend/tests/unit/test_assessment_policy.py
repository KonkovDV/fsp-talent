"""Grade test v2: the CAT engine (3PL, EAP, classification stop) and the grade policy of TZ section 2."""
from __future__ import annotations

import collections
import random
from datetime import UTC, datetime, timedelta

import pytest

from app.items import LEVEL_B
from app.items.registry import BLUEPRINTS, CONCEPT_MAX_SHARE, FAMILIES
from app.models.assessment import GRADE_COOLDOWN_DAYS
from app.seed.questions import QUESTIONS, balanced
from app.services import cat
from app.services.assessment import decide_grade, passed_target
from app.services.categorization import assign_category
from app.services.item_monitor import KeyStats, calibrate_offset, leave_family_out

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def _simulate(theta: float, spec: str, target: str, rng: random.Random, answer=None) -> tuple[cat.State, cat.Outcome]:
    state = cat.State(spec=spec, target=target)
    while not cat.evaluate(state).done:
        ch = cat.choose(state, rng)
        correct = answer(ch) if answer else rng.random() < cat.p3(theta, ch.a, ch.b, ch.c)
        state.responses.append(cat.Response(ch.a, ch.b, ch.c, correct))
        state.families_used[ch.family.id] += 1
        state.topics_used[ch.family.topic] += 1
        state.concept_used += ch.family.kind == "concept"
    return state, cat.decide(state)


# --- IRT ---------------------------------------------------------------------------------------

def test_3pl_has_a_guessing_floor_and_is_monotone():
    assert cat.p3(-10, 1.4, 0.0, 0.25) == pytest.approx(0.25, abs=1e-3)
    assert cat.p3(10, 1.4, 0.0, 0.25) == pytest.approx(1.0, abs=1e-3)
    assert cat.p3(0, 1.4, 0.0, 0.25) == pytest.approx(0.625)
    ps = [cat.p3(t, 1.2, 0.3, 0.25) for t in (-2, -1, 0, 1, 2)]
    assert ps == sorted(ps)


def test_information_peaks_slightly_above_difficulty_with_guessing():
    grid = [x / 100 for x in range(-300, 300)]
    best = max(grid, key=lambda t: cat.info3(t, 1.4, 0.0, 0.25))
    assert 0.0 < best < 0.5


def test_posterior_moves_with_answers_and_narrows():
    items = [cat.Response(1.4, b, 0.25, True) for b in (-1, 0, 1)]
    up = cat.posterior(items)
    down = cat.posterior([cat.Response(r.a, r.b, r.c, False) for r in items])
    assert up.theta > 0 > down.theta
    assert cat.posterior(items * 5).se < cat.posterior(items).se < 1.0


def test_no_answers_means_undecided_not_a_grade():
    state = cat.State(spec="backend", target="middle")
    v = cat.evaluate(state)
    assert not v.done and v.p_pass == pytest.approx(0.5, abs=0.03)
    assert not cat.decide(state).passed


# --- CAT behaviour -----------------------------------------------------------------------------

@pytest.mark.parametrize("spec", sorted(BLUEPRINTS))
def test_sessions_respect_length_specialization_and_concept_cap(spec):
    rng = random.Random(1)
    for theta in (-2.0, -0.5, 0.4, 1.6):
        state, _ = _simulate(theta, spec, "middle", rng)
        assert cat.MIN_ITEMS <= state.n <= cat.MAX_ITEMS
        assert all(spec in FAMILIES[f].specs for f in state.families_used), state.families_used
        assert state.concept_used <= CONCEPT_MAX_SHARE * state.n + 1


def test_strong_candidates_pass_and_weak_fail():
    rng = random.Random(2)
    strong = [_simulate(1.3, "backend", "middle", rng)[1].passed for _ in range(40)]
    weak = [_simulate(-1.5, "backend", "middle", rng)[1].passed for _ in range(40)]
    assert sum(strong) >= 36 and sum(weak) <= 2


def test_random_guessing_does_not_pass():
    rng = random.Random(3)
    passed = [_simulate(0, "frontend", "junior", rng, answer=lambda ch: rng.random() < 0.25)[1].passed
              for _ in range(60)]
    assert sum(passed) <= 2


def test_skipping_or_all_wrong_confirms_nothing():
    rng = random.Random(4)
    for target in ("junior", "middle", "senior", "lead"):
        state, out = _simulate(0, "ml", target, rng, answer=lambda ch: False)
        assert not out.passed and out.earned is None and state.n >= cat.MIN_ITEMS


def test_upgrade_needs_strong_evidence():
    rng = random.Random(5)
    ups = [_simulate(1.2, "backend", "middle", rng)[1].upgraded for _ in range(40)]   # true grade: senior
    stay = [_simulate(0.0, "backend", "middle", rng)[1].upgraded for _ in range(40)]  # true grade: middle
    # "Уверенно": the upgrade is deliberately conservative (P ≥ 0.9), so not every true senior gets it.
    assert sum(ups) >= 12 and sum(stay) <= 1


def test_randomesque_choice_spreads_items():
    keys = collections.Counter()
    for seed in range(200):
        state = cat.State(spec="backend", target="middle")
        ch = cat.choose(state, random.Random(seed))
        keys[cat.item_key(ch.family, ch.level)] += 1
    assert len(keys) >= 3 and max(keys.values()) < 120


def test_blocked_keys_are_never_served():
    rng = random.Random(6)
    blocked = {f"py_eval:{lvl}" for lvl in range(1, 6)}
    for _ in range(30):
        state = cat.State(spec="backend", target="middle")
        for _ in range(10):
            ch = cat.choose(state, rng, blocked=blocked)
            assert ch.family.id != "py_eval"
            state.responses.append(cat.Response(ch.a, ch.b, ch.c, True))
            state.families_used[ch.family.id] += 1
            state.topics_used[ch.family.topic] += 1
            state.concept_used += ch.family.kind == "concept"


def test_skill_scores_need_three_items():
    rows = [(("Python",), True)] * 3 + [(("SQL",), True)] * 2
    assert cat.skill_scores(rows) == {"Python": 1.0}


# --- Leak monitoring and calibration -------------------------------------------------------------

def test_drift_alarm_fires_on_leak_not_on_honest_answers():
    honest, leaked = KeyStats(), KeyStats()
    rng = random.Random(7)
    for _ in range(200):
        p = 0.5
        honest.add(p, rng.random() < p)
        leaked.add(p, True)
    assert not honest.alarm and leaked.alarm and leaked.z > 10


def test_leave_family_out_keeps_the_leak_visible():
    # 6 right answers from a leaked family, 6 wrong from the rest: with the family left out, ability is low,
    # so the leaked answers look surprising (low expected P).
    rows = [("leak:3", "leak", 1.4, 0.0, 0.25, True)] * 6 + [("other:3", "other", 1.4, 0.0, 0.25, False)] * 6
    exp = {k: p for k, p, _ in leave_family_out(rows, prior_mean=0.0)}
    assert exp["leak:3"] < 0.5


def test_calibration_recovers_a_difficulty_shift():
    rng = random.Random(8)
    rows = []
    for _ in range(600):
        theta = rng.gauss(0, 1)
        rows.append((theta, 1.4, 0.0, 0.25, rng.random() < cat.p3(theta, 1.4, 0.6, 0.25)))
    assert calibrate_offset(rows) == pytest.approx(0.6, abs=0.2)


def test_levels_cover_every_grade_cut():
    for cut in cat.CUTS.values():
        assert min(abs(b - cut) for b in LEVEL_B.values()) <= 0.6


# --- Policy (TZ section 2) -----------------------------------------------------------------------

def test_passed_target():
    assert passed_target("middle", "middle") and passed_target("senior", "middle")
    assert not passed_target("junior", "middle") and not passed_target(None, "junior")


def test_failed_attempt_changes_nothing_and_does_not_lock():
    d = decide_grade("middle", "junior", "senior", NOW)
    assert d.assessed_grade == "middle" and not d.applied and d.locked_until is None
    assert d.reason == "not_passed"
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
    d = decide_grade("middle", "senior", "middle", NOW)
    assert d.assessed_grade == "senior" and d.upgraded


def test_test_never_lowers_a_confirmed_grade():
    d = decide_grade("senior", "junior", "junior", NOW)
    assert d.assessed_grade == "senior" and not d.applied and d.reason == "kept_higher_grade"


def test_repeat_of_same_grade_does_not_restart_cooldown():
    d = decide_grade("middle", "middle", "middle", NOW)
    assert not d.applied and d.locked_until is None and d.reason == "confirmed_again"


# --- Static concept pool -------------------------------------------------------------------------

def test_balanced_bank_keeps_content_and_spreads_right_answers():
    bank = [balanced(q, i) for i, q in enumerate(QUESTIONS)]
    for original, shuffled in zip(QUESTIONS, bank, strict=True):
        right = next(o["text"] for o in original["options"] if o["id"] == original["correct_option"])
        assert next(o["text"] for o in shuffled["options"] if o["id"] == shuffled["correct_option"]) == right
    counts = collections.Counter(q["correct_option"] for q in bank)
    assert max(counts.values()) / len(bank) <= 0.30


# --- Category -------------------------------------------------------------------------------------

def test_assessed_grade_outranks_declaration_and_experience():
    category = assign_category(["Python", "Go"], [], experience_years=10, declared_grade="lead",
                               assessed_grade="middle")
    assert category["grade"] == "middle" and category["grade_source"] == "assessed"
    declared = assign_category(["Python", "Go"], [], declared_grade="lead")
    assert declared["grade_source"] == "declared"


def test_survey_specialization_decides_the_role():
    category = assign_category(["Python", "Go", "FastAPI"], [], specialization="security")
    assert category["primary_role"] == "security"
    assert any("опроса" in line for line in category["explanation"])
