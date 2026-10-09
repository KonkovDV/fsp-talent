"""A hidden tab and a grade appeal are marks. Neither one assigns a grade."""
from app.services.session_marks import dispute_error, note_copy, note_tab_leave


def test_hiding_the_tab_is_counted_and_does_not_name_a_grade():
    flags = note_tab_leave({"mode": "grade"})
    assert flags["tab_leaves"] == 1
    assert "grade_assigned" not in flags
    capped = note_tab_leave({"tab_leaves": 30})
    assert capped["tab_leaves"] == 30
    copied = note_copy({"mode": "grade"})
    assert copied["copies"] == 1 and "grade_assigned" not in copied
    assert note_copy({"copies": 30})["copies"] == 30


def test_only_the_owner_of_a_finished_test_can_dispute_it_once():
    assert dispute_error("completed", False, False) == "not_found"
    assert dispute_error("in_progress", True, False) == "not_finished"
    assert dispute_error("completed", True, True) == "already"
    assert dispute_error("completed", True, False) is None
