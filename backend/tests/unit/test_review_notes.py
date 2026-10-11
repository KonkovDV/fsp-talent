"""Review marks are words for a person. They do not name a grade change."""
from app.api.v1.assessment import _review_notes


def test_marks_say_the_grade_stays():
    notes = _review_notes({"pace_review": "py_eval", "variant_review": "py_eval", "integrity_review": True})
    assert len(notes) == 4 and notes[0].startswith("Уровень риска честности: высокий")
    assert all("Грейд не изменён" in line for line in notes)
    assert _review_notes({}) == []
