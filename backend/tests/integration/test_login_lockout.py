"""Stand audit I-01: a stranger's wrong passwords do not lock the owner out (per account × address)."""
from __future__ import annotations

import httpx

from app.core.redis_client import get_redis
from app.main import app
from app.models import Employer
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def _try(address: str, email: str, password: str) -> int:
    transport = httpx.ASGITransport(app=app, client=(address, 40000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/auth/employer/token", data={"username": email, "password": password})
        return r.status_code


async def _retry_after(address: str, email: str, password: str) -> str | None:
    transport = httpx.ASGITransport(app=app, client=(address, 40000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/auth/employer/token", data={"username": email, "password": password})
        return r.headers.get("retry-after")


async def test_wrong_passwords_from_one_address_do_not_lock_another(db):
    tag = stamp()
    email = f"dbtest-lock-{tag}@example.com"
    company = Employer(email=email, company_name=f"Lock {tag}", password_hash=PASSWORD_HASH, email_verified_at=now())
    db.add(company)
    await db.commit()
    redis = await get_redis()
    for key in await redis.keys(f"auth:*{email}*"):
        await redis.delete(key)
    try:
        codes = [await _try("203.0.113.9", email, "wrong") for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429
        assert await _try("198.51.100.7", email, "dbtest-pass") == 200
        assert await _try("203.0.113.9", email, "dbtest-pass") == 429
        # The minute window answers first with its own Retry-After (60). Once it is gone the 15-minute
        # per-address lock is still there and says how long it lasts.
        for key in await redis.keys(f"auth:login:*{email}*"):
            await redis.delete(key)
        assert await _retry_after("203.0.113.9", email, "dbtest-pass") == "900"
    finally:
        await db.rollback()
        await wipe_people([], [company.id])


async def test_the_account_cap_spares_demo_accounts_and_decays(db, monkeypatch):
    """100 failures lock an ordinary account, never a published demo one; an expired lock starts over."""
    from datetime import UTC, datetime, timedelta

    from app.core.config import settings
    from app.services.login_lock import ACCOUNT_LOCK_AFTER
    # The exemption exists only on a demo stand; do not depend on the DEMO_MODE of the test environment.
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    tag = stamp()
    plain = Employer(email=f"dbtest-cap-{tag}@example.com", company_name=f"Cap {tag}", password_hash=PASSWORD_HASH,
                     email_verified_at=now(), failed_logins=ACCOUNT_LOCK_AFTER - 1)
    demo = Employer(email=f"dbtest-cap-{tag}@lock.demo", company_name=f"Demo {tag}", password_hash=PASSWORD_HASH,
                    email_verified_at=now(), failed_logins=ACCOUNT_LOCK_AFTER - 1)
    db.add_all([plain, demo])
    await db.commit()
    try:
        assert await _try("203.0.113.20", plain.email, "wrong") == 401
        assert await _try("198.51.100.20", plain.email, "dbtest-pass") == 429     # locked as a whole
        assert await _try("203.0.113.21", demo.email, "wrong") == 401
        assert await _try("198.51.100.21", demo.email, "dbtest-pass") == 200      # demo never locked
        # The lock runs out: one more wrong password does not close the account again.
        from sqlalchemy import update
        await db.execute(update(Employer).where(Employer.id == plain.id)
                         .values(locked_until=datetime.now(UTC) - timedelta(minutes=1)))
        await db.commit()
        assert await _try("203.0.113.22", plain.email, "wrong") == 401
        assert await _try("198.51.100.22", plain.email, "dbtest-pass") == 200
    finally:
        await db.rollback()
        await wipe_people([], [plain.id, demo.id])


async def test_one_address_is_limited_across_accounts(db, monkeypatch):
    """30 sign-in attempts a minute from one address outside the demo stand, 300 on it."""
    from app.core.config import settings
    redis = await get_redis()
    for key in await redis.keys("auth:login-ip:*"):
        await redis.delete(key)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    codes = [await _try("203.0.113.30", f"nobody-{i}@example.com", "x") for i in range(31)]
    assert codes[:30] == [401] * 30 and codes[30] == 429
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    codes = [await _try("203.0.113.31", f"nobody-{i}@example.com", "x") for i in range(31)]
    assert 429 not in codes
