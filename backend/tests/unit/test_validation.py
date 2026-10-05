"""The validation procedure runs and its headline numbers stay inside agreed bounds."""
from app.validation.assessment import run


def test_assessment_validation_bounds():
    r = run(n=1500, seed=3)
    assert r.false_upgrades < 0.03          # "уверенно": upgrades need a 1 SE margin
    assert r.retest_pass_fail > 0.65        # consistency of the pass/fail outcome
    assert r.right_rate_high - r.right_rate_low > 0.3   # the bank separates weak from strong
    assert r.constant_answer_best <= 0.30   # no answer letter dominates
