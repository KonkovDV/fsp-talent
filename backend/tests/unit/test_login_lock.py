"""Wrong passwords from one address must not lock the account for everyone."""
import asyncio
from datetime import UTC, datetime, timedelta

from app.services import login_lock
from app.services.login_lock import ACCOUNT_LOCK_AFTER, next_failure, still_locked

NOW = datetime(2026, 10, 10, tzinfo=UTC)


def test_five_wrong_passwords_no_longer_lock_the_account():
    count, until = next_failure(4, NOW)
    assert count == 5 and until is None


def test_the_account_locks_only_at_the_nist_cap():
    count, until = next_failure(ACCOUNT_LOCK_AFTER - 1, NOW)
    assert count == ACCOUNT_LOCK_AFTER and until == NOW + timedelta(minutes=15)
    assert ACCOUNT_LOCK_AFTER <= 100          # NIST SP 800-63B §5.2.2
    assert still_locked(until, NOW + timedelta(minutes=1))
    assert not still_locked(until, NOW + timedelta(minutes=16))
    assert not still_locked(None, NOW)


def test_a_published_demo_account_is_never_locked_as_a_whole():
    assert next_failure(10_000, NOW, lockable=False)[1] is None
    assert login_lock.demo_protected("jury1@demo.talent", "@demo.talent,.demo", True)
    assert login_lock.demo_protected("hr@sibcode.demo", "@demo.talent,.demo", True)
    assert not login_lock.demo_protected("jury1@demo.talent", "@demo.talent,.demo", False)
    assert not login_lock.demo_protected("ivan@mail.ru", "@demo.talent,.demo", True)


class _Redis:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def delete(self, key):
        self.data.pop(key, None)

    def pipeline(self, transaction=False):
        outer = self

        class _P:
            def incr(self, key):
                outer.data[key] = int(outer.data.get(key) or 0) + 1

            def expire(self, key, seconds):
                pass

            async def execute(self):
                return []
        return _P()


def test_the_lock_is_per_address():
    redis = _Redis()
    attacker = login_lock.pair_key("participant", "jury1@demo.talent", "203.0.113.9")
    owner = login_lock.pair_key("participant", "jury1@demo.talent", "198.51.100.7")

    async def run():
        for _ in range(login_lock.PAIR_LOCK_AFTER):
            await login_lock.pair_failed(redis, attacker)
        assert await login_lock.pair_locked(redis, attacker)
        assert not await login_lock.pair_locked(redis, owner)
        await login_lock.pair_cleared(redis, attacker)
        assert not await login_lock.pair_locked(redis, attacker)
    asyncio.run(run())


def test_an_expired_account_lock_starts_the_count_again():
    expired = NOW - timedelta(minutes=1)
    count, until = next_failure(ACCOUNT_LOCK_AFTER, NOW, locked_until=expired)
    assert count == 1 and until is None
    active = NOW + timedelta(minutes=5)
    assert next_failure(ACCOUNT_LOCK_AFTER, NOW, locked_until=active)[1] is not None


def test_retry_after_counts_down_to_the_end_of_the_lock():
    until = NOW + timedelta(minutes=15)
    assert login_lock.seconds_left(until, NOW) == 900
    assert login_lock.seconds_left(until, NOW + timedelta(minutes=14, seconds=59, microseconds=500)) == 1
    assert login_lock.seconds_left(until.replace(tzinfo=None), NOW + timedelta(minutes=5)) == 600
