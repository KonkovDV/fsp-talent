"""Company API keys: shown once, stored as a hash, read-only export only."""
from __future__ import annotations

import inspect
import uuid
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1 import integrations
from app.core import rls
from app.models import EmployerApiKey
from app.services.api_keys import key_hash, new_key, well_formed


async def _no_limit(*_a, **_k):
    return False


def test_new_key_is_well_formed_and_only_its_hash_is_kept():
    full, prefix, digest = new_key()
    assert well_formed(full) and full.startswith(f"fspk_{prefix}_")
    assert digest == key_hash(full) and len(digest) == 64 and full not in digest
    assert new_key()[0] != full


def test_model_has_no_plaintext_column():
    cols = set(EmployerApiKey.__table__.columns.keys())
    assert "key_hash" in cols and "key" not in cols and "secret" not in cols


def test_schema_has_table_with_row_level_security():
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0001_initial.py").read_text()
    assert "CREATE TABLE public.employer_api_keys" in sql
    assert "public.employer_api_keys FORCE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY employer_api_keys_actor" in sql


@pytest.mark.parametrize("bad", ["", "nope", "fspk_short_x", "fspk_12345678_" + "a" * 10])
def test_malformed_key_is_not_well_formed(bad):
    assert not well_formed(bad)


async def test_no_session_and_no_key_is_401():
    with pytest.raises(ApiError) as e:
        await integrations.employer_or_api_key(None, None)
    assert e.value.status_code == 401


async def test_malformed_key_is_401_without_lookup(monkeypatch):
    monkeypatch.setattr(integrations, "too_many", _no_limit)

    async def boom(_full):
        raise AssertionError("must not hit the database")
    monkeypatch.setattr(integrations, "_key_owner", boom)
    with pytest.raises(ApiError) as e:
        await integrations.employer_or_api_key(None, "garbage")
    assert e.value.status_code == 401


async def test_unknown_or_revoked_key_is_401(monkeypatch):
    monkeypatch.setattr(integrations, "too_many", _no_limit)

    async def none(_full):
        return None
    monkeypatch.setattr(integrations, "_key_owner", none)
    with pytest.raises(ApiError) as e:
        await integrations.employer_or_api_key(None, new_key()[0])
    assert e.value.status_code == 401


async def test_valid_key_scopes_rows_to_its_company(monkeypatch):
    owner = uuid.uuid4()
    monkeypatch.setattr(integrations, "too_many", _no_limit)

    async def found(_full):
        return owner
    monkeypatch.setattr(integrations, "_key_owner", found)
    token = rls.set_rls()
    try:
        out = await integrations.employer_or_api_key(None, new_key()[0])
        assert out == {"sub": str(owner), "role": "employer", "via": "api_key"}
        scope = rls.current()
        assert scope["employer_id"] == str(owner) and not scope["bypass"]
    finally:
        rls.reset_rls(token)


async def test_rate_limited_key_is_429(monkeypatch):
    async def limited(*_a, **_k):
        return True
    monkeypatch.setattr(integrations, "too_many", limited)
    with pytest.raises(ApiError) as e:
        await integrations.employer_or_api_key(None, new_key()[0])
    assert e.value.status_code == 429


def test_only_export_accepts_a_key():
    for route in integrations.router.routes:
        deps = inspect.signature(route.endpoint).parameters
        uses_key = any(getattr(p.default, "dependency", None) is integrations.employer_or_api_key
                       for p in deps.values())
        assert uses_key == (route.path == "/employer/integrations/export"), route.path


def test_key_list_never_returns_the_key():
    row = EmployerApiKey(id=uuid.uuid4(), employer_id=uuid.uuid4(), prefix="abcd1234", key_hash="0" * 64,
                         label="ATS", created_at=__import__("datetime").datetime.now(__import__("datetime").UTC))
    out = integrations._key_out(row)
    assert "key" not in out and "key_hash" not in out and out["prefix"] == "fspk_abcd1234_…"


def test_a_key_past_its_term_is_not_usable_and_an_old_key_without_term_still_is():
    from datetime import UTC, datetime, timedelta

    from app.services.api_keys import MAX_TERM_DAYS, TERM_DAYS, usable
    now = datetime.now(UTC)
    assert TERM_DAYS <= MAX_TERM_DAYS <= 365
    assert usable(SimpleNamespace(revoked_at=None, expires_at=now + timedelta(days=1)), now)
    assert not usable(SimpleNamespace(revoked_at=None, expires_at=now - timedelta(seconds=1)), now)
    assert not usable(SimpleNamespace(revoked_at=now, expires_at=None), now)
    assert usable(SimpleNamespace(revoked_at=None, expires_at=None), now)


def test_the_term_is_bounded_and_listed():
    from datetime import UTC, datetime, timedelta

    from pydantic import ValidationError
    assert integrations.KeyIn().days == 90
    for bad in (0, 366):
        with pytest.raises(ValidationError):
            integrations.KeyIn(days=bad)
    now = datetime.now(UTC)
    row = EmployerApiKey(id=uuid.uuid4(), employer_id=uuid.uuid4(), prefix="abcd1234", key_hash="0" * 64,
                         label=None, created_at=now - timedelta(days=100), expires_at=now - timedelta(days=10))
    out = integrations._key_out(row)
    assert out["expired"] is True and out["expires_at"].startswith(str((now - timedelta(days=10)).date()))


async def test_create_key_sets_the_term_and_skips_expired_keys_in_the_limit(monkeypatch):
    from datetime import UTC, datetime, timedelta

    class Db:
        def __init__(self):
            self.added, self.where = [], ""

        async def scalars(self, stmt):
            self.where = str(stmt.compile(compile_kwargs={"literal_binds": False}))
            return []

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            pass

    db = Db()
    out = await integrations.create_key(integrations.KeyIn(days=30), {"sub": str(uuid.uuid4()), "role": "employer"}, db)
    [row] = db.added
    assert "expires_at" in db.where
    assert timedelta(days=29) < row.expires_at - datetime.now(UTC) <= timedelta(days=30)
    assert out["key"].startswith("fspk_") and out["expired"] is False


async def test_an_expired_key_does_not_sign_in(monkeypatch):
    from datetime import UTC, datetime, timedelta

    full = new_key()[0]
    row = SimpleNamespace(employer_id=uuid.uuid4(), revoked_at=None, expires_at=datetime.now(UTC) - timedelta(hours=1),
                          last_used_at=None)

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def scalar(self, stmt):
            return row

        async def get(self, model, ident):
            raise AssertionError("an expired key must not reach the owner lookup")

        async def commit(self):
            raise AssertionError("an expired key must not be marked as used")

    monkeypatch.setattr(integrations, "AsyncSessionLocal", Session)
    assert await integrations._key_owner(full) is None
