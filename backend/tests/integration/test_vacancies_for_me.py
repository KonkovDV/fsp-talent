"""V-N1: a candidate without a test sees open vacancies, newest first; a minor without consent cannot apply.

The apply route agrees with the card: what the list marks needs_test answers 403, what it allows is accepted.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.api.v1.vacancies import apply, vacancies_for_me
from app.models import Application, Employer, Participant, Vacancy
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def _setup(db, tag: str, **person):
    company = Employer(company_name=f"Тест {tag}", email=f"dbtest-{tag}@example.com", password_hash=PASSWORD_HASH)
    db.add(company)
    await db.flush()
    base = dict(email=f"dbtest-{tag}-p@example.com", display_name="Без теста", password_hash=PASSWORD_HASH,
                email_verified_at=now(), is_minor=False, birth_date=date(1998, 5, 1), is_visible=True)
    base.update(person)
    p = Participant(**base)
    db.add(p)
    t = now()
    rows = [
        Vacancy(employer_id=company.id, title=f"{tag} старая", role="backend", grade="senior",
                allows_minors=True, created_at=t - timedelta(days=2)),
        Vacancy(employer_id=company.id, title=f"{tag} новая", role="backend", grade="middle", grade_match="any",
                allows_minors=True, created_at=t - timedelta(hours=1)),
        Vacancy(employer_id=company.id, title=f"{tag} закрыта", role="backend", grade="middle",
                allows_minors=True, is_open=False, created_at=t),
    ]
    db.add_all(rows)
    await db.commit()
    return company, p


async def _cleanup(db, company, p):
    company_id, person_id = company.id, p.id
    await db.rollback()
    await db.execute(delete(Application).where(Application.candidate_id == person_id))
    await db.execute(delete(Vacancy).where(Vacancy.employer_id == company_id))
    await db.commit()
    await wipe_people([person_id], [company_id])


async def test_without_a_test_the_open_vacancies_are_listed_newest_first(db):
    tag = stamp()
    company, p = await _setup(db, tag)
    try:
        cards = await vacancies_for_me({"sub": str(p.id), "role": "participant"}, db)
        mine = [c for c in cards if c["title"].startswith(tag)]
        assert [c["title"] for c in mine] == [f"{tag} новая", f"{tag} старая"]
        assert all(c["match"] == "not_assessed" for c in mine)
        by_title = {c["title"]: c for c in mine}
        assert by_title[f"{tag} новая"]["can_apply"] is True        # grade_match any
        assert by_title[f"{tag} старая"]["can_apply"] is False      # graded: the test comes first
        assert by_title[f"{tag} старая"]["needs_test"] is True
    finally:
        await _cleanup(db, company, p)


async def test_a_minor_without_consent_sees_but_cannot_apply(db):
    tag = stamp()
    company, p = await _setup(db, tag, birth_date=date.today().replace(year=date.today().year - 15),
                              is_minor=True, minor_consent_given=False)
    try:
        cards = await vacancies_for_me({"sub": str(p.id), "role": "participant"}, db)
        mine = [c for c in cards if c["title"].startswith(tag)]
        assert mine and all(c["can_apply"] is False for c in mine)
    finally:
        await _cleanup(db, company, p)


async def test_apply_follows_the_card_without_a_test(db):
    tag = stamp()
    company, p = await _setup(db, tag)
    current = {"sub": str(p.id), "role": "participant"}
    try:
        cards = {c["title"]: c for c in await vacancies_for_me(current, db) if c["title"].startswith(tag)}
        graded, any_grade = cards[f"{tag} старая"], cards[f"{tag} новая"]
        with pytest.raises(HTTPException) as refused:
            await apply(uuid.UUID(str(graded["id"])), current, db)
        assert refused.value.status_code == 403 and "тестом" in refused.value.detail
        await apply(uuid.UUID(str(any_grade["id"])), current, db)
        await db.commit()
        rows = list(await db.scalars(select(Application).where(Application.candidate_id == uuid.UUID(current["sub"]))))
        assert [r.status for r in rows] == ["applied"]
    finally:
        await _cleanup(db, company, p)
