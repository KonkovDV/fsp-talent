"""The simulation runs end to end and its headline numbers stay inside agreed bounds."""
from app.validation.assessment import run


def test_assessment_validation_bounds():
    r = run(n=250, seed=3)
    assert r.clean.accuracy_clear > 0.80        # clear cases (> 0.5 from the cut) are classified right
    assert r.clean.false_pass < 0.15            # overclaimers rarely pass
    assert r.clean.false_upgrade < 0.04
    assert r.guesser_pass < 0.02
    assert r.clean.mean_len <= 20
    assert r.clean.concept_share <= 0.30
