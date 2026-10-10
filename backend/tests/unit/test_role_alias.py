from app.api.v1.search import implied_role


def test_a_russian_role_word_fills_an_empty_filter():
    assert implied_role("нужен бэкенд в команду", None) == "backend"
    assert implied_role("frontend разработчик", None) == "frontend"


def test_an_explicit_role_and_a_skill_word_stay_put():
    assert implied_role("нужен бэкенд", "frontend") == "frontend"
    assert implied_role("знает Python", None) is None
    assert implied_role(None, None) is None
