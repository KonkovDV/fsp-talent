"""SDK-03: only a test-confirmed grade opens a graded vacancy; a declared grade does not (ТЗ 2.1, #289)."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from app.api.v1.vacancies import apply, vacancies_for_me
from app.models import Application, CategoryAssignment, Employer, Participant, Vacancy
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def _setup(db, tag: str, grade_source: str):
    company = Employer(company_name=f"Тест {tag}", email=f"dbtest-{tag}@example.com", password_hash=PASSWORD_HASH)
    db.add(company)
    await db.flush()
    p = Participant(email=f"dbtest-{tag}-p@example.com", display_name="Грейд", password_hash=PASSWORD_HASH,
                    email_verified_at=now(), is_minor=False, birth_date=date(1998, 5, 1), is_visible=True)
    db.add(p)
    await db.flush()
    db.add(CategoryAssignment(participant_id=p.id, primary_role="backend", grade="middle", grade_source=grade_source))
    graded = Vacancy(employer_id=company.id, title=f"{tag} мидл", role="backend", grade="middle")
    db.add(graded)
    await db.commit()
    return company, p, graded


async def _cleanup(db, company_id, participant_id):
    await db.rollback()
    await db.execute(delete(Application).where(Application.candidate_id == participant_id))
    await db.execute(delete(Vacancy).where(Vacancy.employer_id == company_id))
    await db.commit()
    await wipe_people([participant_id], [company_id])


@pytest.mark.parametrize("source", ["declared", "default"])
async def test_a_declared_grade_does_not_open_a_graded_vacancy(db, source):
    tag = stamp()
    company, p, graded = await _setup(db, tag, source)
    ids = (company.id, p.id)
    vacancy_id = graded.id
    user = {"sub": str(p.id), "role": "participant"}
    try:
        card = next(c for c in await vacancies_for_me(user, db) if c["title"] == f"{tag} мидл")
        assert card["match"] == "not_assessed"
        assert card["needs_test"] is True and card["can_apply"] is False
        with pytest.raises(HTTPException) as err:
            await apply(vacancy_id, user, db)
        assert err.value.status_code == 403
        assert "тест" in err.value.detail
    finally:
        await _cleanup(db, *ids)


async def test_an_assessed_grade_opens_the_graded_vacancy(db):
    tag = stamp()
    company, p, graded = await _setup(db, tag, "assessed")
    ids = (company.id, p.id)
    vacancy_id = graded.id
    user = {"sub": str(p.id), "role": "participant"}
    try:
        card = next(c for c in await vacancies_for_me(user, db) if c["title"] == f"{tag} мидл")
        assert card["match"] == "matched"
        assert card["needs_test"] is False and card["can_apply"] is True
        await apply(vacancy_id, user, db)
    finally:
        await _cleanup(db, *ids)
