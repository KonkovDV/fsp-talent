"""Idempotency-Key: same body replays, a different body conflicts, Redis down fails closed."""
import json

import pytest
from redis.exceptions import RedisError

from app.core import idempotency


class _Redis:
    def __init__(self, fail: bool = False):
        self.data: dict[str, str] = {}
        self.fail = fail

    async def get(self, key):
        if self.fail:
            raise RedisError("down")
        return self.data.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if self.fail:
            raise RedisError("down")
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def delete(self, key):
        self.data.pop(key, None)


@pytest.fixture
def redis(monkeypatch):
    store = _Redis()

    async def get():
        return store

    monkeypatch.setattr(idempotency, "get_redis", get)
    return store


async def test_the_same_key_replays_and_a_different_body_conflicts(redis):
    assert await idempotency.idem_begin("offer:1", "k", "aaa") is None
    await idempotency.idem_finish("offer:1", "k", "aaa", 201, {"id": "1"})
    stored = await idempotency.idem_begin("offer:1", "k", "aaa")
    assert stored["status"] == 201 and stored["body"]["id"] == "1"
    with pytest.raises(idempotency.IdempotencyConflict):
        await idempotency.idem_begin("offer:1", "k", "bbb")
    assert json.loads(redis.data["idem:offer:1:k"])["status"] == 201


async def test_a_missing_key_does_nothing():
    assert await idempotency.idem_begin("offer:1", None, "aaa") is None
    await idempotency.idem_finish("offer:1", None, "aaa", 201, {})


async def test_redis_down_fails_closed(monkeypatch):
    store = _Redis(fail=True)

    async def get():
        return store

    monkeypatch.setattr(idempotency, "get_redis", get)
    with pytest.raises(idempotency.IdempotencyUnavailable):
        await idempotency.idem_begin("offer:1", "k", "aaa")
