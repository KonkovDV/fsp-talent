"""A second registration of an unconfirmed address must not replace the password."""
from types import SimpleNamespace

from app.api.v1.auth import repeat_registration


def test_unconfirmed_account_is_left_as_it_is():
    account = SimpleNamespace(email_verified_at=None)
    assert repeat_registration(account) is True


def test_new_address_and_confirmed_account_go_through_registration():
    assert repeat_registration(None) is False
    assert repeat_registration(SimpleNamespace(email_verified_at=object())) is False
