import pytest

from app.services.code_profile import clean_github, code_profile_line


def test_the_card_line_does_not_contain_the_login():
    assert code_profile_line(None) is None
    line = code_profile_line("Octocat")
    assert line is not None
    assert "Octocat" not in line
    assert "согласия" in line


def test_the_login_drops_an_at_sign_and_rejects_spaces():
    assert clean_github(" @Octocat ") == "Octocat"
    assert clean_github("") is None
    with pytest.raises(ValueError):
        clean_github("bad login")
