"""Login limits fail closed when Redis is down; search limits stay open so a demo still runs."""
import pytest

from app.core import ratelimit


async def test_closed_limit_raises_and_an_open_one_allows(monkeypatch):
    async def down():
        raise ConnectionError("redis down")

    monkeypatch.setattr(ratelimit, "get_redis", down)
    with pytest.raises(ratelimit.RateLimitUnavailable):
        await ratelimit.too_many("auth:login:a@b.c", fail_closed=True)
    assert await ratelimit.too_many("search:candidates:1") is False
