"""A failed test at the shown, unconfirmed grade lowers the grade the need-fit reads."""
from app.services.matching import CandidateFacts, NeedSpec, grade_for_matching, reason_source, score
from app.services.session_marks import latest_failed_targets
from app.validation.matching import _facts, make_dataset

NEED = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL"))
SKILLS = {"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}


def _cand(**kw) -> CandidateFacts:
    base = dict(role="backend", grade="middle", grade_source="declared", skills=dict(SKILLS))
    base.update(kw)
    return CandidateFacts(**base)


def test_failed_target_steps_the_unconfirmed_grade_down():
    assert grade_for_matching("middle", "declared", "middle") == ("junior", True)
    assert grade_for_matching("senior", "declared", "middle") == ("junior", True)
    assert grade_for_matching("intern", "declared", "intern") == ("intern", True)


def test_confirmed_grade_and_a_failed_step_up_stay():
    assert grade_for_matching("middle", "assessed", "middle") == ("middle", False)
    assert grade_for_matching("middle", "declared", "senior") == ("middle", False)
    assert grade_for_matching("middle", "declared", None) == ("middle", False)
    assert grade_for_matching("middle", "declared", "guru") == ("middle", False)
    assert grade_for_matching(None, "default", "middle") == (None, False)


def test_failed_candidate_ranks_below_the_same_declared_profile_and_says_why():
    plain = score(NEED, _cand())
    failed = score(NEED, _cand(failed_grade="middle"))
    assert failed.score < plain.score
    line = next(r for r in failed.reasons if r.code == "GRADE_TEST_FAILED")
    assert line.tone == "minus" and "не подтверждён" in line.text and "джуниор" in line.text
    assert reason_source("GRADE_TEST_FAILED") == "тест"
    # The card is not hidden and not told it was never tested.
    assert not any(r.code == "UNTESTED" for r in failed.reasons)
    assert failed.confirmed == 0


def test_failed_at_middle_fits_a_junior_need():
    junior = NeedSpec(role="backend", grade="junior", skills=NEED.skills)
    plain = score(junior, _cand())
    failed = score(junior, _cand(failed_grade="middle"))
    assert failed.score > plain.score
    assert any(r.code == "GRADE_TEST_FAILED" for r in failed.reasons)


def test_ablation_without_the_test_ignores_the_failure():
    plain = score(NEED, _cand(), use_test=False)
    failed = score(NEED, _cand(failed_grade="middle"), use_test=False)
    assert failed.score == plain.score
    assert not any(r.code == "GRADE_TEST_FAILED" for r in failed.reasons)


def test_only_the_newest_grade_test_per_specialization_counts():
    rows = [
        ("p", "backend", "senior", {"mode": "express", "outcome": "not_passed"}),
        ("p", "backend", "middle", {"outcome": "not_passed"}),
        ("p", "backend", "junior", {"outcome": "not_passed"}),
        ("q", "backend", "middle", {"outcome": "first_confirmation"}),
        ("q", "backend", "middle", {"outcome": "not_passed"}),
        ("r", "frontend", "middle", {"vacancy_id": "v", "outcome": "vacancy_test"}),
        ("r", "frontend", "senior", {"outcome": "not_passed"}),
        ("s", None, "middle", {"outcome": "not_passed"}),
    ]
    failed = latest_failed_targets(rows)
    assert failed == {("p", "backend"): "middle", ("r", "frontend"): "senior"}


def test_benchmark_observes_the_failed_attempt():
    data = make_dataset(200, 10, seed=5)
    failed = [c for c in data["candidates"] if c["observed"].get("failed_grade")]
    assert failed
    for c in failed:
        o = c["observed"]
        assert o["grade_source"] == "declared" and o["test_p"] is None and o["failed_grade"] == o["grade"]
        assert _facts(c).failed_grade == o["grade"]
    assert all("failed_grade" not in c["observed"] for c in data["candidates"]
               if c["observed"]["grade_source"] == "assessed")


def test_evidence_guard_is_a_sign_rule_with_a_pooled_interval():
    from app.validation import matching as v
    rows = v.evaluate(v.make_dataset(60, 6, seed=3))
    good = {key: {"per_seed": {1: 0.1}, "mean": 0.1, "low": 0.01, "high": 0.2, "n": 6}
            for key, _ in v.GUARD_ABLATIONS}
    bad = {**good, "no_fsp": {"per_seed": {1: 0.1}, "mean": 0.1, "low": -0.01, "high": 0.2, "n": 6}}
    assert not any("Spearman" in f for f in v.checks_ok(rows, True, good))
    assert any("no_fsp" in f for f in v.checks_ok(rows, True, bad))
    assert any("Spearman" in f for f in v.checks_ok(rows, True, None))
    assert "| без оси ФСП |" in v.guard_markdown(good)
