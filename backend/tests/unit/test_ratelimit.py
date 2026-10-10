"""Login limits fail closed when Redis is down; search limits stay open so a demo still runs."""
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1 import auth
from app.core import ratelimit


async def test_closed_limit_raises_and_an_open_one_allows(monkeypatch):
    async def down():
        raise ConnectionError("redis down")

    monkeypatch.setattr(ratelimit, "get_redis", down)
    with pytest.raises(ratelimit.RateLimitUnavailable):
        await ratelimit.too_many("auth:login:a@b.c", fail_closed=True)
    assert await ratelimit.too_many("search:candidates:1") is False


def _peer(ip: str):
    return SimpleNamespace(client=SimpleNamespace(host=ip), headers={})


async def test_one_ip_cannot_close_registration_for_another(monkeypatch):
    store: dict[str, int] = {}

    async def fake(bucket, limit=5, window_seconds=60, *, fail_closed=False):
        store[bucket] = store.get(bucket, 0) + 1
        return store[bucket] > limit

    monkeypatch.setattr(auth, "too_many", fake)
    here = _peer("1.1.1.1")
    for n in range(10):
        await auth._charge_registration(here, f"person{n}@example.com", "participant")
    with pytest.raises(ApiError) as caught:
        await auth._charge_registration(here, "more@example.com", "participant")
    assert caught.value.status_code == 429
    await auth._charge_registration(_peer("8.8.8.8"), "other@example.com", "participant")
