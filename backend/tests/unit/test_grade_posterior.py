"""The grade posterior sums to one, and π = 0 does not reorder confirmed grades."""
import pytest

from app.core.config import settings
from app.services.grade_posterior import (
    GRADES,
    expected_rel,
    fail_table,
    mass_assessed,
    mass_declared,
    smooth_pi,
)
from app.services.matching import GRADES as MATCH_GRADES
from app.services.matching import CandidateFacts, NeedSpec, score


def test_grade_names_match_the_ranker():
    assert GRADES == MATCH_GRADES


def test_probability_mass_sums_to_one():
    for shown in GRADES:
        assert sum(mass_assessed(shown, 0.82, 0.2).values()) == pytest.approx(1.0)
        assert sum(mass_declared(shown, 0.37).values()) == pytest.approx(1.0)
    lead = mass_assessed("lead", 0.9, 0.4)
    assert lead[GRADES.index("lead") + 1] == 0.0
    assert sum(lead.values()) == pytest.approx(1.0)


def test_smooth_pi_falls_back_to_the_overall_share():
    assert smooth_pi(0, 0, 0.4) == pytest.approx(0.4)
    assert smooth_pi(10, 20, 0.4) == pytest.approx((10 + 20 * 0.4) / 40)


def test_higher_pass_probability_raises_the_expected_grade():
    low = expected_rel("middle", mass_assessed("middle", 0.5, 0.0))
    high = expected_rel("middle", mass_assessed("middle", 0.9, 0.0))
    assert high > low


def test_zero_fail_rate_does_not_reorder_confirmed_grades(monkeypatch):
    need = NeedSpec(role="backend", grade="middle", skills=("Python",))
    strong = CandidateFacts(role="backend", grade="middle", grade_source="assessed",
                            skills={"Python": "test_confirmed"}, test_p=0.95, test_spec="backend", p_up=0.0)
    weak = CandidateFacts(role="backend", grade="middle", grade_source="assessed",
                          skills={"Python": "test_confirmed"}, test_p=0.80, test_spec="backend", p_up=0.0)
    monkeypatch.setattr(settings, "GRADE_MODEL", "legacy")
    legacy = score(need, strong).score - score(need, weak).score
    monkeypatch.setattr(settings, "GRADE_MODEL", "expected")
    expected = score(need, strong).score - score(need, weak).score
    assert legacy > 0 and expected > 0

    sure = CandidateFacts(role="backend", grade="middle", grade_source="assessed",
                          skills={"Python": "test_confirmed"}, test_p=1.0, test_spec="backend", p_up=0.0)
    monkeypatch.setattr(settings, "GRADE_MODEL", "legacy")
    before = score(need, sure).score
    monkeypatch.setattr(settings, "GRADE_MODEL", "expected")
    after = score(need, sure).score
    assert after == pytest.approx(before)


def test_declared_card_names_the_first_try_pass_rate(monkeypatch):
    monkeypatch.setattr(settings, "GRADE_MODEL", "expected")
    need = NeedSpec(role="backend", grade="middle")
    person = CandidateFacts(role="backend", grade="middle", grade_source="declared", fail_rate=0.25)
    result = score(need, person)
    assert any("сдают 75 %" in line and "×0.75" in line for line in result.info)


def test_fail_table_uses_the_cell_and_the_overall_share():
    attempts = [("backend", "middle", False)] * 10 + [("backend", "middle", True)] * 10
    attempts += [("qa", "junior", True)] * 5
    overall, cells = fail_table(attempts)
    assert overall == pytest.approx(10 / 25)
    assert cells[("backend", "middle")] == pytest.approx(smooth_pi(10, 20, overall))
