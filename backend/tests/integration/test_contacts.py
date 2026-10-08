"""Contacts open only after the candidate accepts the invitation."""
import pytest
from fastapi import HTTPException

from app.api.v1.offers import reveal_contacts
from app.models import Employer, Offer, Participant
from app.services.identity import give_consent
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def test_contacts_wait_for_acceptance(db):
    tag = stamp()
    person = Participant(
        email=f"dbtest-contact-{tag}@example.com",
        display_name="Контакты",
        password_hash=PASSWORD_HASH,
        email_verified_at=now(),
        is_minor=False,
        is_visible=True,
        public_profile=False,
        specialization="backend",
        declared_grade="middle",
        job_search="active",
        survey_at=now(),
        work_goal="job",
        phone="+79990001122",
        region="Новосибирск",
    )
    company = Employer(
        email=f"dbtest-hr-{tag}@example.com",
        company_name=f"Интеграция {tag}",
        password_hash=PASSWORD_HASH,
        email_verified_at=now(),
    )
    db.add(person)
    db.add(company)
    await db.flush()
    await give_consent(db, "participant", person.id, "pd_candidate")
    offer = Offer(
        employer_id=company.id, candidate_id=person.id,
        salary_from_gross=100_000, salary_to_gross=150_000,
        currency="RUB", role="backend", work_format="remote",
        contact_method="почта", status="pending",
    )
    db.add(offer)
    await db.commit()
    current = {"sub": str(company.id)}
    try:
        with pytest.raises(HTTPException) as denied:
            await reveal_contacts(offer.id, current, db)
        assert denied.value.status_code == 403
        offer.status = "accepted"
        await db.commit()
        opened = await reveal_contacts(offer.id, current, db)
        assert opened["email"] == person.email
        assert opened["phone"] == person.phone
        assert opened["contacts_revealed_at"]
    finally:
        await wipe_people([person.id], [company.id])
