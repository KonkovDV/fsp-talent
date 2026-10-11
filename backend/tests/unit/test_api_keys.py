"""Company API keys: shown once, stored as a hash, read-only export only."""
from __future__ import annotations

import inspect
import uuid

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
