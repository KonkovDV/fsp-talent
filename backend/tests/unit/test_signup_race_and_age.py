"""audit-3 P3-1 (race answers 202, not 409 email_taken) and P3-2 (the 18+ checkbox opens nothing adult-only)."""
import inspect
from datetime import date

from app.api.v1 import auth, passport, vacancies
from app.models import Participant


def test_checkbox_without_birth_date_is_not_adult():
    ticked = Participant(is_minor=False, birth_date=None)
    assert not ticked.adult_confirmed()
    assert Participant(is_minor=False, birth_date=date(1990, 1, 1)).adult_confirmed()
    child = Participant(is_minor=False, birth_date=date(date.today().year - 10, 1, 1))
    assert not child.adult_confirmed()


def test_adult_only_actions_need_the_birth_date():
    assert "not adult_confirmed(person)" in inspect.getsource(passport.issue_my_passport)
    assert "is_minor\": participant.minor_now()" not in inspect.getsource(vacancies)


def test_the_signup_race_does_not_reveal_the_address():
    for handler in (auth.register_participant, auth.register_employer):
        source = inspect.getsource(handler)
        assert 'ApiError(409, "email_taken")' not in source and "except IntegrityError" in source
