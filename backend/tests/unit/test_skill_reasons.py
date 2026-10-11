"""F24: a declared skill without a test confirmation has its own reason, apart from a missing one."""
from app.services.matching import CandidateFacts, NeedSpec, reason_source, score

NEED = NeedSpec(role="backend", grade="middle", skills=("Python", "PostgreSQL", "Docker"))


def _cand(skills: dict) -> CandidateFacts:
    return CandidateFacts(role="backend", grade="middle", grade_source="declared", skills=skills)


def test_untested_confirmed_and_missing_are_three_reasons():
    m = score(NEED, _cand({"Python": "test_confirmed", "PostgreSQL": "self_reported"}))
    codes = {r.code: r for r in m.reasons}
    assert "Python" in codes["VERIFIED_SKILL"].text
    assert codes["SKILL_UNTESTED"].text == "Заявлены, тестом не подтверждены: PostgreSQL"
    assert codes["SKILL_UNTESTED"].tone == "info"
    assert "Docker" in codes["SKILL_GAP"].text and "PostgreSQL" not in codes["SKILL_GAP"].text
    assert reason_source("SKILL_UNTESTED") == "заявлено"


def test_resume_quote_and_import_are_untested_but_related_is_not():
    m = score(NEED, _cand({"Python": "resume_confirmed", "PostgreSQL": "file_import", "Kubernetes": "self_reported"}))
    line = next(r.text for r in m.reasons if r.code == "SKILL_UNTESTED")
    assert "Python" in line and "PostgreSQL" in line and "Docker" not in line


def test_the_new_line_does_not_move_the_score():
    skills = {"Python": "self_reported", "PostgreSQL": "resume_confirmed"}
    m = score(NEED, _cand(skills))
    assert any(r.code == "SKILL_UNTESTED" for r in m.reasons)
    confirmed = score(NEED, _cand({"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}))
    assert not any(r.code == "SKILL_UNTESTED" for r in confirmed.reasons)
    assert m.score < confirmed.score
