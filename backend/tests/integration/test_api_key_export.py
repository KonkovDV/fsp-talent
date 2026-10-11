"""A company's API key reads its own export under its own row scope; a revoked key does not."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

import app.api.v1.integrations as integrations
from app.api.errors import ApiError
from app.core.database import AsyncSessionLocal
from app.core.rls import bypass_rls, reset_rls, set_rls
from app.models import Employer, EmployerApiKey
from app.services.api_keys import new_key
from tests.integration.conftest import PASSWORD_HASH, stamp


async def _no_limit(*_a, **_k):
    return False


async def _employer(tag: str) -> uuid.UUID:
    token = bypass_rls()
    try:
        async with AsyncSessionLocal() as s:
            e = Employer(id=uuid.uuid4(), company_name=f"K{tag}", email=f"k{tag}@t.test",
                         password_hash=PASSWORD_HASH)
            s.add(e)
            await s.commit()
            return e.id
    finally:
        reset_rls(token)


async def _key(employer_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    full, prefix, digest = new_key()
    token = bypass_rls()
    try:
        async with AsyncSessionLocal() as s:
            row = EmployerApiKey(id=uuid.uuid4(), employer_id=employer_id, prefix=prefix, key_hash=digest,
                                 created_at=datetime.now(UTC))
            s.add(row)
            await s.commit()
            return full, row.id
    finally:
        reset_rls(token)


async def test_key_scopes_export_and_revocation_closes_it(monkeypatch):
    monkeypatch.setattr(integrations, "too_many", _no_limit)
    mine, theirs = await _employer(stamp()), await _employer(stamp())
    try:
        full, key_id = await _key(mine)
        await _key(theirs)
        scope = set_rls()
        try:
            current = await integrations.employer_or_api_key(None, full)
            assert current["sub"] == str(mine)
            async with AsyncSessionLocal() as s:
                seen = {row.employer_id for row in await s.scalars(select(EmployerApiKey))}
                assert seen == {mine}            # row-level scope, not the bypass
                assert await integrations.export("json", current, s) == {"items": []}
        finally:
            reset_rls(scope)
        token = bypass_rls()
        try:
            async with AsyncSessionLocal() as s:
                row = await s.get(EmployerApiKey, key_id)
                assert row.last_used_at is not None
                row.revoked_at = datetime.now(UTC)
                await s.commit()
        finally:
            reset_rls(token)
        with pytest.raises(ApiError) as e:
            await integrations.employer_or_api_key(None, full)
        assert e.value.status_code == 401
    finally:
        token = bypass_rls()
        try:
            async with AsyncSessionLocal() as s:
                await s.execute(delete(Employer).where(Employer.id.in_([mine, theirs])))
                await s.commit()
        finally:
            reset_rls(token)
