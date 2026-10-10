"""Demo guest accounts: off outside the demo stand, consents first, sessions close after 48 hours."""
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import Response

from app.api import deps
from app.api.errors import ApiError
from app.api.v1 import auth
from app.core.config import settings
from app.services import guest
from app.services.identity import required_kinds
from app.services.mail import send_mail


class Db:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self):
        self.commits += 1


def _request():
    return SimpleNamespace(headers={}, client=SimpleNamespace(host="203.0.113.5"))


@pytest.fixture
def open_door(monkeypatch):
    async def allow(*_args, **_kwargs):
        return None

    given = []

    async def consent(db, role, subject_id, kind, request):
        given.append((role, kind))

    monkeypatch.setattr(auth, "_limit", allow)
    monkeypatch.setattr(auth, "give_consent", consent)
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    return given


async def test_guest_is_off_outside_the_demo_stand(open_door, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    with pytest.raises(ApiError) as off:
        await auth.guest_login(auth.GuestIn(role="participant", consents=list(required_kinds("participant"))),
                               _request(), Response(), Db())
    assert off.value.status_code == 404


async def test_guest_needs_the_registration_consents(open_door):
    db = Db()
    with pytest.raises(ApiError) as missing:
        await auth.guest_login(auth.GuestIn(role="participant", consents=[]), _request(), Response(), db)
    assert missing.value.code == "consent_required" and not db.added


@pytest.mark.parametrize("role", ["participant", "employer"])
async def test_guest_gets_an_empty_account_for_two_days(open_door, role):
    db = Db()
    response = Response()
    kinds = list(required_kinds(role))
    out = await auth.guest_login(auth.GuestIn(role=role, consents=kinds), _request(), response, db)
    account = db.added[0]
    assert out.role == role and out.access_token and out.refresh_token == ""
    assert "fsp_refresh=" in response.headers["set-cookie"]
    until = datetime.fromisoformat(out.guest_until)
    assert timedelta(hours=47) < until - datetime.now(UTC) <= guest.GUEST_TTL
    assert open_door == [(role, kind) for kind in kinds] and db.commits == 1
    if role == "participant":
        assert account.email is None and account.is_visible is False
    else:
        assert account.email.endswith("@guest.invalid") and account.email_verified_at is not None
        assert not auth.password_matches("!", account.password_hash)


async def test_an_expired_guest_cannot_use_or_refresh_the_session():
    now = datetime.now(UTC)
    person = SimpleNamespace(id=uuid.uuid4(), deleted_at=None, token_epoch=0, guest_until=now - timedelta(seconds=1))

    class One:
        async def get(self, model, ident, **kwargs):
            return person

    with pytest.raises(ValueError):
        await deps._open_account(One(), {"sub": str(person.id), "role": "participant", "ep": 0})
    assert not auth.account_can_refresh(person)
    person.guest_until = now + timedelta(hours=1)
    assert await deps._open_account(One(), {"sub": str(person.id), "role": "participant", "ep": 0}) is person
    assert auth.account_can_refresh(person)


async def test_no_letter_leaves_for_a_reserved_address(monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "MAIL_MODE", "smtp")
    monkeypatch.setattr("app.services.mail._send_smtp", lambda message: sent.append(message))
    await send_mail("guest-abc@guest.invalid", "Тема", "Текст")
    assert sent == []
