from app.services.assessment import fast_correct_suspicious, note_pace
from app.services.session_marks import (
    integrity_flagged,
    integrity_level,
    integrity_line,
    latest_grade_flags,
    note_paste,
    penalised,
)


def test_only_a_grade_test_at_moderate_risk_lowers_the_place():
    assert integrity_flagged({"pace_review": "loops"}) is True
    assert integrity_flagged({"tab_leaves": 2}) is False          # one signal alone: low
    assert integrity_flagged({"tab_leaves": 2, "copies": 1}) is True
    assert integrity_flagged({"copies": 3}) is False
    assert integrity_flagged({"tab_leaves": 4, "copies": 2, "mode": "express"}) is False
    assert integrity_flagged({"pace_review": "x", "vacancy_id": "v"}) is False
    score, note = penalised(0.8, {"fast_correct": 2})
    assert score == 0.68 and "умеренный" in note and "Грейд не изменён" in note
    assert penalised(0.8, {"tab_leaves": 1}) == (0.8, None)
    assert penalised(0.8, {}) == (0.8, None)


def test_w6_levels_follow_the_points():
    assert integrity_level({"tab_leaves": 1})["level"] == "none"       # one hidden tab is no signal
    assert integrity_level({"tab_leaves": 2})["level"] == "low"
    two_fast_and_paste = note_paste({"fast_correct": 2})
    assert integrity_level(two_fast_and_paste) == {"level": "moderate", "points": 3,
                                                   "signals": ["pastes", "fast_correct"]}
    assert integrity_level({"variant_review": "f", "fast_correct": 2})["level"] == "high"
    assert integrity_level({"variant_review": "f", "fast_correct": 2, "mode": "express"})["level"] == "none"


def test_w6_line_names_signals_not_guilt():
    line = integrity_line({"tab_leaves": 3})
    assert line.startswith("Уровень риска честности: низкий") and "Место не меняется" in line
    assert "списал" not in line
    assert integrity_line({}) is None


def test_note_paste_is_capped_and_keeps_grade_fields():
    flags = {"grade": "middle"}
    for _ in range(40):
        flags = note_paste(flags)
    assert flags["pastes"] == 30 and flags["grade"] == "middle"


def test_g2_fast_correct_depends_on_theta_and_item_time():
    assert fast_correct_suspicious(0.8, 5.0, 180) is False      # easy for this candidate: not flagged
    assert fast_correct_suspicious(0.2, 100.0, 180) is False    # hard but slow: not flagged
    assert fast_correct_suspicious(0.2, 10.0, 180) is True      # hard and fast: flagged
    assert fast_correct_suspicious(None, 1.0, 180) is None      # no θ: fall back to the fixed rule
    easy = note_pace({}, "f", correct=True, elapsed=2.0, kind="code", expected_p=0.9, time_limit=180)
    assert "fast_correct" not in easy
    hard = note_pace({}, "f", correct=True, elapsed=20.0, kind="concept", expected_p=0.1, time_limit=180)
    assert hard["fast_correct"] == 1
    wrong = note_pace({}, "f", correct=False, elapsed=2.0, kind="code", expected_p=0.1, time_limit=180)
    assert "fast_correct" not in wrong


def test_a_later_trial_does_not_hide_the_grade_test_mark():
    rows = [
        ("p", {"mode": "express", "tab_leaves": 9}),
        ("p", {"tab_leaves": 2}),
        ("q", {"vacancy_id": "v", "pace_review": "x"}),
    ]
    marks = latest_grade_flags(rows)
    assert marks["p"]["tab_leaves"] == 2
    assert "q" not in marks


def test_simulated_false_alarms_stay_under_two_percent():
    from app.validation.integrity import run

    report = run(1500, 2026, 0.5)
    assert report["honest"]["ci95"][1] <= 0.02
    assert report["leak"]["moderate_plus"] > 0.5
