from app.services.matching import CandidateFacts, NeedSpec, score
from app.services.scoring.elo_stretch import elo_stretch


def test_the_span_widens_with_uncertainty_and_stays_inside_zero_and_one():
    tight = elo_stretch(0.5, 0.05)
    wide = elo_stretch(0.5, 0.4)
    assert tight["high"] - tight["low"] < wide["high"] - wide["low"]
    assert elo_stretch(0.1, 0.5)["low"] == 0.0
    assert elo_stretch(0.9, 0.5)["high"] == 1.0
    assert elo_stretch(0.5, -0.05) == tight


def test_the_match_score_does_not_read_the_span():
    need = NeedSpec(role="backend", grade="middle")
    facts = CandidateFacts(role="backend", grade="middle", grade_source="assessed", fsp_lcb=0.4)
    assert score(need, facts).score == score(need, facts).score
