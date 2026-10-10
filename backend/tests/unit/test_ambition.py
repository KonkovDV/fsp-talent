from app.services.ambition import ambition_note
from app.services.matching import CandidateFacts, NeedSpec, score


def test_two_signs_write_a_line_and_one_sign_does_not():
    assert ambition_note("junior", "active", {"Python": "self_reported"}, None) is None
    line = ambition_note("intern", "active", {"Python": "test_confirmed"}, "job")
    assert line and "Грейд" in line
    assert ambition_note("senior", "active", {"Python": "test_confirmed", "Go": "test_confirmed",
                                              "SQL": "test_confirmed", "Kafka": "test_confirmed"}, "job") is None


def test_the_line_does_not_move_the_score():
    need = NeedSpec(role="backend", grade="junior", skills=("Python",))
    facts = CandidateFacts(role="backend", grade="junior", grade_source="declared",
                           skills={"Python": "self_reported"})
    before = score(need, facts).score
    assert ambition_note("junior", "open", {"Python": "self_reported"}, None) is None
    assert score(need, facts).score == before
