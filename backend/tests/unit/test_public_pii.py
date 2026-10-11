"""No /public route hands out a person's data around the publication consent."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from fastapi import Request
from sqlalchemy.dialects import postgresql

from app.api.errors import ApiError
from app.api.v1 import public
from app.core.ratelimit import RateLimitUnavailable

# Routes that touch Participant without the named-page filter, and why that is safe.
NO_PERSON_DATA = {
    "/public/jury-free": "demo stand only; answers a jury account address, not a candidate",
    "/public/categories/{role}/{grade}/ranking": "anonymous places and test numbers, no id or name",
    "/public/stats": "whole-stand totals (count of rows), no id, name or slice",
    "/public/guardian-consent": "the guardian's signed one-time token is the authorization",
}


def _request() -> Request:
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("10.0.0.1", 9)}, receive)


def test_every_public_route_with_person_data_applies_the_public_filter():
    for route in public.router.routes:
        src = inspect.getsource(route.endpoint)
        if "Participant" not in src or route.path in NO_PERSON_DATA:
            continue
        assert "_public_filter()" in src, route.path


class _Capture:
    def __init__(self, person=None):
        self.statements: list = []
        self.person = person

    async def scalar(self, stmt):
        self.statements.append(stmt)
        return self.person

    async def scalars(self, stmt):
        self.statements.append(stmt)
        return []


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


async def test_achievements_lookup_requires_public_profile_consent_and_adult(monkeypatch):
    async def allow(*_a, **_k):
        return False
    monkeypatch.setattr(public, "too_many", allow)
    db = _Capture()
    body = await public.telegram_achievements(_request(), "FSP001", db)
    sql = _sql(db.statements[0])
    assert "public_profile IS true" in sql
    assert "pd_distribution" in sql and "withdrawn_at IS NULL" in sql
    assert "birth_date IS NOT NULL" in sql and "deleted_at IS NULL" in sql
    # A hidden or unknown ID answers like an ID without results: no oracle for which IDs exist.
    assert body == public.achievement_digest("FSP001", [])


async def test_achievements_lists_only_registry_lines(monkeypatch):
    async def allow(*_a, **_k):
        return False
    monkeypatch.setattr(public, "too_many", allow)
    db = _Capture(person=SimpleNamespace(id="00000000-0000-0000-0000-000000000001"))
    await public.telegram_achievements(_request(), "FSP001", db)
    assert "trust_level = 'verified_fsp'" in _sql(db.statements[1])


async def test_achievements_rate_limit_fails_closed(monkeypatch):
    async def down(*_a, **kw):
        assert kw.get("fail_closed") is True
        raise RateLimitUnavailable("x")
    monkeypatch.setattr(public, "too_many", down)
    with pytest.raises(ApiError) as err:
        await public.telegram_achievements(_request(), "FSP001", _Capture())
    assert err.value.status_code == 503


async def test_achievements_limits_per_ip_and_per_site(monkeypatch):
    seen = []

    async def count(bucket, limit, window_seconds, **_k):
        seen.append((bucket, limit))
        return bucket.endswith(":site")
    monkeypatch.setattr(public, "too_many", count)
    with pytest.raises(ApiError) as err:
        await public.telegram_achievements(_request(), "FSP001", _Capture())
    assert err.value.status_code == 429
    assert seen == [("public:telegram:achievements:10.0.0.1", public.TELEGRAM_PER_IP_PER_MINUTE),
                    ("public:telegram:achievements:site", public.TELEGRAM_SITE_PER_MINUTE)]
