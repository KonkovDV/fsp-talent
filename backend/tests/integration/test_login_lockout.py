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
    finally:
        await db.rollback()
        await wipe_people([], [company.id])
