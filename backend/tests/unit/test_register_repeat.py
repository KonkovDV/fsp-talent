"""A second registration of an unconfirmed address must not replace the password."""
from types import SimpleNamespace

from starlette.responses import Response

from app.api.v1.auth import attach_refresh, clear_refresh, repeat_registration
from app.core.config import settings


def test_unconfirmed_account_is_left_as_it_is():
    account = SimpleNamespace(email_verified_at=None)
    assert repeat_registration(account) is True


def test_new_address_and_confirmed_account_go_through_registration():
    assert repeat_registration(None) is False
    assert repeat_registration(SimpleNamespace(email_verified_at=object())) is False


def test_logout_clears_the_refresh_cookie_with_the_same_flags(monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    stored = Response()
    attach_refresh(stored, "refresh-token")
    cleared = Response()
    clear_refresh(cleared)
    gone = cleared.headers["set-cookie"]
    assert "Secure" in stored.headers["set-cookie"]
    assert "Secure" in gone
    assert "HttpOnly" in gone
    assert "Path=/api/v1/auth" in gone
    assert "Max-Age=0" in gone
