import pytest

from app.services.qa_probe import judge_cases


def test_sound_cases_kill_the_planted_defects_and_leave_the_grade():
    report = judge_cases([("-1", "0"), ("150", "100"), ("50", "50")])
    assert report["accepted"] == 3 and report["rejected"] == 0
    assert report["grade_unchanged"] is True
    assert set(report["killed"]) == {
        "нет нижней границы", "нет верхней границы", "всегда ноль", "сдвиг на единицу",
    }


def test_a_wrong_expectation_does_not_count_as_a_catch():
    report = judge_cases([("50", "49"), ("nope", "0")])
    assert report["accepted"] == 0 and report["rejected"] == 2 and report["killed"] == []
    with pytest.raises(ValueError):
        judge_cases([("1", "1")] * 6)
