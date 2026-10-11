"""SEC3-05: a birth date before 1900 is refused at signup and in the profile."""
from datetime import date

import pytest
from pydantic import ValidationError

from app.api.v1.auth import ParticipantRegister
from app.api.v1.candidates import ProfileUpdate


@pytest.mark.parametrize("born", [date(1, 1, 1), date(1899, 12, 31)])
def test_a_birth_date_before_1900_is_refused(born):
    with pytest.raises(ValidationError):
        ProfileUpdate(birth_date=born)
    with pytest.raises(ValidationError):
        ParticipantRegister(email="a@example.com", password="Very-long-pass-123", display_name="А",
                            is_adult=True, birth_date=born)


def test_1900_and_later_pass_the_schema():
    assert ProfileUpdate(birth_date=date(1900, 1, 1)).birth_date == date(1900, 1, 1)
    assert ProfileUpdate(birth_date=None).birth_date is None
