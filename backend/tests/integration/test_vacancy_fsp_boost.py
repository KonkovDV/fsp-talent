"""SDK-01: a vacancy with an FSP discipline is open to a candidate without FSP history (ТЗ 2: a boost, not a gate)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete

from app.api.v1.vacancies import apply, vacancies_for_me
from app.models import Application, CategoryAssignment, Employer, Participant, Vacancy
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def test_a_candidate_without_fsp_sees_and_applies_to_a_discipline_vacancy(db):
    tag = stamp()
    company = Employer(company_name=f"Тест {tag}", email=f"dbtest-{tag}@example.com", password_hash=PASSWORD_HASH)
    db.add(company)
    await db.flush()
    p = Participant(email=f"dbtest-{tag}-p@example.com", display_name="Без ФСП", password_hash=PASSWORD_HASH,
                    email_verified_at=now(), is_minor=False, birth_date=date(1998, 5, 1), is_visible=True)
    db.add(p)
    await db.flush()
    db.add(CategoryAssignment(participant_id=p.id, primary_role="backend", grade="middle", grade_source="assessed"))
    vacancy = Vacancy(employer_id=company.id, title=f"{tag} алгоритмы", role="backend", grade="middle",
                      discipline="algorithmic", min_rank="II")
    db.add(vacancy)
    await db.commit()
    company_id, participant_id, vacancy_id = company.id, p.id, vacancy.id
    user = {"sub": str(participant_id), "role": "participant"}
    try:
        card = next(c for c in await vacancies_for_me(user, db) if c["title"] == f"{tag} алгоритмы")
        assert card["can_apply"] is True and card["fsp_match"] is False
        assert any("не обязательны" in w for w in card["why"])
        await apply(vacancy_id, user, db)
    finally:
        await db.rollback()
        await db.execute(delete(Application).where(Application.candidate_id == participant_id))
        await db.execute(delete(Vacancy).where(Vacancy.employer_id == company_id))
        await db.commit()
        await wipe_people([participant_id], [company_id])
