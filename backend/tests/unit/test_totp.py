"""Moderation desk second factor: RFC 6238 vectors, one use per code, the desk stays shut without it."""
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1 import moderation
from app.services import totp

RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890", RFC 6238 appendix B, SHA-1


@pytest.mark.parametrize(("unix", "code"), [
    (59, "287082"), (1111111109, "081804"), (1234567890, "005924"), (2000000000, "279037"),
])
def test_rfc_6238_vectors(unix, code):
    moment = datetime.fromtimestamp(unix, UTC)
    assert totp.hotp(RFC_SECRET, totp.step_at(moment)) == code
    assert totp.accept(RFC_SECRET, code, moment, None) == totp.step_at(moment)


def test_a_code_works_once_and_only_near_its_time():
    moment = datetime.fromtimestamp(1234567890, UTC)
    step = totp.accept(RFC_SECRET, "005924", moment, None)
    assert totp.accept(RFC_SECRET, "005924", moment, step) is None
    assert totp.accept(RFC_SECRET, "005924", moment + timedelta(seconds=30), None) == step
    assert totp.accept(RFC_SECRET, "005924", moment + timedelta(minutes=5), None) is None
    assert totp.accept(RFC_SECRET, "00592", moment, None) is None
    assert totp.accept(RFC_SECRET, "abcdef", moment, None) is None


def test_the_secret_is_sealed_to_its_company_and_the_uri_is_standard():
    secret = totp.new_secret()
    owner = str(uuid.uuid4())
    stored = totp.seal_secret(owner, secret)
    assert secret not in stored and totp.open_secret(owner, stored) == secret
    with pytest.raises(ValueError):
        totp.open_secret(str(uuid.uuid4()), stored)
    uri = totp.provisioning_uri(secret, "hr@sibcode.demo")
    assert uri.startswith("otpauth://totp/") and f"secret={secret}" in uri and "period=30" in uri


class Db:
    def __init__(self, employer):
        self.employer, self.commits = employer, 0

    async def get(self, model, ident, **kwargs):
        return self.employer if ident == self.employer.id else None

    async def commit(self):
        self.commits += 1


@pytest.fixture
def desk(monkeypatch):
    async def never(*args, **kwargs):
        return False
    monkeypatch.setattr(moderation, "too_many", never)
    monkeypatch.setattr(moderation.settings, "DEMO_MODE", True)
    eid = uuid.uuid4()
    secret = totp.new_secret()
    employer = SimpleNamespace(id=eid, email="hr@sibcode.demo", totp_secret=totp.seal_secret(str(eid), secret),
                               totp_last_step=None, totp_verified_at=None)
    return SimpleNamespace(db=Db(employer), current={"sub": str(eid)}, secret=secret, employer=employer)


async def test_the_desk_asks_for_a_code_and_opens_for_fifteen_minutes(desk):
    with pytest.raises(ApiError) as shut:
        await moderation.complaints(desk.current, desk.db)
    assert shut.value.status_code == 403 and shut.value.code == "totp_required"
    state = await moderation.factor_state(desk.current, desk.db)
    assert state == {"enrolled": True, "unlocked": False, "unlocked_until": None}

    with pytest.raises(ApiError) as wrong:
        await moderation.unlock_desk(moderation.TotpIn(code="000000"), desk.current, desk.db)
    assert wrong.value.code == "totp_invalid"
    code = totp.hotp(desk.secret, totp.step_at(datetime.now(UTC)))
    opened = await moderation.unlock_desk(moderation.TotpIn(code=code), desk.current, desk.db)
    assert opened["unlocked"] and desk.db.commits == 1
    with pytest.raises(ApiError) as replay:
        await moderation.unlock_desk(moderation.TotpIn(code=code), desk.current, desk.db)
    assert replay.value.code == "totp_invalid"

    desk.employer.totp_verified_at = datetime.now(UTC) - totp.UNLOCK - timedelta(seconds=1)
    with pytest.raises(ApiError):
        await moderation.complaints(desk.current, desk.db)


async def test_without_enrollment_the_demo_desk_works_as_before(desk):
    desk.employer.totp_secret = None
    await moderation._desk(desk.current, desk.db)
    with pytest.raises(ApiError) as nothing:
        await moderation.unlock_desk(moderation.TotpIn(code="123456"), desk.current, desk.db)
    assert nothing.value.status_code == 409
