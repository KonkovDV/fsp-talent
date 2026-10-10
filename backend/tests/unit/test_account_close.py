from app.services.account_close import close_allowed


def test_a_password_account_needs_the_word_and_the_password():
    assert close_allowed("удалить", True, True) is None
    assert close_allowed("нет", True, True) == "word"
    assert close_allowed("удалить", True, False) == "password"


def test_an_account_without_a_password_closes_on_the_word():
    assert close_allowed("удалить", False, False) is None
