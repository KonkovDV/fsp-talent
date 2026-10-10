from app.services.hiring_practice import card_fields, clean_answers, sees_senior


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


def test_a_thin_survey_hides_city_and_the_long_profile():
    thin = {"feedback": False, "platform_interview": True, "task_review": False, "salary_written": True}
    assert card_fields(thin, show_city=True, show_fsp=True, show_experience=True) == (False, False, False)
    assert card_fields(None, show_city=True, show_fsp=False, show_experience=True) == (True, False, True)
    full = {key: True for key in ("feedback", "platform_interview", "task_review", "salary_written")}
    assert card_fields(full, show_city=False, show_fsp=True, show_experience=False) == (False, True, False)
