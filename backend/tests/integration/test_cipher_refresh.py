"""A refreshed or expired object shows the opened contact, not the stored ciphertext.

The cipher opened contacts only on "load"; refresh() and a reload of expired attributes fire "refresh",
so PATCH /employer/me returned "enc:v1:..." as the e-mail and any code reusing that value broke.
"""
from __future__ import annotations

import httpx

from app.main import app
from app.models import Employer
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("192.0.2.40", 40000)),
                             base_url="http://test")


async def test_profile_edit_returns_the_plain_email_and_login_still_works(db):
    tag = stamp()
    email = f"dbtest-enc-{tag}@example.com"
    company = Employer(email=email, company_name=f"Enc {tag}", password_hash=PASSWORD_HASH, email_verified_at=now())
    db.add(company)
    await db.commit()
    try:
        async with await _client() as client:
            r = await client.post("/api/v1/auth/employer/token", data={"username": email, "password": "dbtest-pass"})
            assert r.status_code == 200
            auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
            r = await client.patch("/api/v1/employer/me", json={"description": "Обновлено"}, headers=auth)
            assert r.status_code == 200
            assert r.json()["email"] == email
            r = await client.post("/api/v1/auth/employer/token", data={"username": email, "password": "dbtest-pass"})
            assert r.status_code == 200
    finally:
        await db.rollback()
        await wipe_people([], [company.id])


async def test_refresh_and_a_reload_open_the_contact(db):
    tag = stamp()
    email = f"dbtest-enc2-{tag}@example.com"
    company = Employer(email=email, company_name=f"Enc2 {tag}", password_hash=PASSWORD_HASH, email_verified_at=now())
    db.add(company)
    await db.commit()
    cid = company.id
    try:
        await db.refresh(company)
        assert company.email == email
        from sqlalchemy import select
        again = await db.scalar(select(Employer).where(Employer.id == company.id)
                                .execution_options(populate_existing=True))
        assert again.email == email
        company.failed_logins = 1                     # a later save keeps the stored row intact
        await db.commit()
        await db.refresh(company)
        assert company.email == email
    finally:
        await db.rollback()
        await wipe_people([], [cid])
