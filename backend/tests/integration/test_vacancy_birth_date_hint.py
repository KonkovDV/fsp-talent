"""SDK-02: without a birth date an adult-only vacancy is closed, and the refusal says what to fill in."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from app.api.v1.vacancies import apply
from app.models import CategoryAssignment, Employer, Participant, Vacancy
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def test_apply_without_a_birth_date_names_the_missing_field(db):
    tag = stamp()
    company = Employer(company_name=f"Тест {tag}", email=f"dbtest-{tag}@example.com", password_hash=PASSWORD_HASH)
    db.add(company)
    await db.flush()
    p = Participant(email=f"dbtest-{tag}-p@example.com", display_name="Без даты", password_hash=PASSWORD_HASH,
                    email_verified_at=now(), is_minor=False, birth_date=None, is_visible=True)
    db.add(p)
    await db.flush()
    db.add(CategoryAssignment(participant_id=p.id, primary_role="backend", grade="middle", grade_source="assessed"))
    vacancy = Vacancy(employer_id=company.id, title=f"{tag} взрослая", role="backend", grade="middle",
                      allows_minors=False)
    db.add(vacancy)
    await db.commit()
    company_id, participant_id, vacancy_id = company.id, p.id, vacancy.id
    try:
        with pytest.raises(HTTPException) as err:
            await apply(vacancy_id, {"sub": str(participant_id), "role": "participant"}, db)
        assert err.value.status_code == 403 and "дату рождения" in err.value.detail
    finally:
        await db.rollback()
        await db.execute(delete(Vacancy).where(Vacancy.employer_id == company_id))
        await db.commit()
        await wipe_people([participant_id], [company_id])
