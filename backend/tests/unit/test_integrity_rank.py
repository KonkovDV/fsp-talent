from app.services.session_marks import INTEGRITY_LINE, integrity_flagged, latest_grade_flags, penalised


def test_only_a_grade_test_with_a_signal_lowers_the_place():
    assert integrity_flagged({"pace_review": "loops"}) is True
    assert integrity_flagged({"tab_leaves": 2}) is True
    assert integrity_flagged({"copies": 3}) is False
    assert integrity_flagged({"tab_leaves": 4, "mode": "express"}) is False
    assert integrity_flagged({"pace_review": "x", "vacancy_id": "v"}) is False
    score, note = penalised(0.8, {"tab_leaves": 1})
    assert score == 0.68 and note == INTEGRITY_LINE
    assert penalised(0.8, {}) == (0.8, None)


def test_a_later_trial_does_not_hide_the_grade_test_mark():
    rows = [
        ("p", {"mode": "express", "tab_leaves": 9}),
        ("p", {"tab_leaves": 2}),
        ("q", {"vacancy_id": "v", "pace_review": "x"}),
    ]
    marks = latest_grade_flags(rows)
    assert marks["p"]["tab_leaves"] == 2
    assert "q" not in marks
