"""One rubric for an industry case and its follow-up. The grade stays put."""
from app.services.industry_case import RUBRIC_BOTH, RUBRIC_CASE, judge, present
from app.services.survey import INDUSTRIES


def test_fintech_follow_up_uses_the_same_rubric():
    shown = present("fintech")
    assert "10 000" in shown["ask"]
    assert "first" not in shown
    good = judge("fintech", "100", "30")
    assert good["rubric"] == RUBRIC_BOTH and good["grade_unchanged"] is True
    partial = judge("fintech", "100", "20")
    assert partial["rubric"] == RUBRIC_CASE and partial["grade_unchanged"] is True


def test_every_industry_has_a_case_and_an_unknown_falls_back():
    for code in INDUSTRIES:
        shown = present(code)
        assert shown["ask"] and shown["follow"] and shown["grade_unchanged"] is True
        assert judge(code, "0", "0")["grade_unchanged"] is True
    assert present("нет такой")["industry"] == "any"
    assert present(None)["industry"] == "any"
