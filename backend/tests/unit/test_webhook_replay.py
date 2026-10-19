"""SEC4: the sandbox receiver accepts one webhook-id once inside the window."""
import asyncio

import app.core.redis_client as rc
from app.services import webhooks


class FakeRedis:
    def __init__(self):
        self.keys = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys[key] = (value, ex)
        return True


def test_same_id_is_rejected_the_second_time(monkeypatch):
    fake = FakeRedis()

    async def get():
        return fake
    monkeypatch.setattr(rc, "get_redis", get)
    assert asyncio.run(webhooks.first_delivery("ep1", "msg_1"))
    assert not asyncio.run(webhooks.first_delivery("ep1", "msg_1"))
    assert asyncio.run(webhooks.first_delivery("ep2", "msg_1"))
    assert all(ex == 2 * webhooks.SKEW_SECONDS for _, ex in fake.keys.values())


def test_redis_down_rejects_the_delivery(monkeypatch):
    async def broken():
        raise ConnectionError("down")
    monkeypatch.setattr(rc, "get_redis", broken)
    assert not asyncio.run(webhooks.first_delivery("ep1", "msg_x"))
