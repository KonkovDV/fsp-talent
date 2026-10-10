from app.services.hiring_practice import clean_answers, sees_senior


def test_missing_answers_keep_the_whole_bank():
    assert sees_senior(None) is True
    assert sees_senior({}) is True


def test_three_yes_answers_see_senior_and_two_do_not():
    yes = {key: True for key in ("feedback", "platform_interview", "task_review", "salary_written")}
    assert sees_senior(yes) is True
    thin = dict(yes)
    thin["feedback"] = False
    thin["task_review"] = False
    assert sees_senior(thin) is False
    assert "score" not in clean_answers(thin)
