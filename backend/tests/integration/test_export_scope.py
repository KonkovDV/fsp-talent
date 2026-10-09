"""Own export under row policies does not see another participant's invitation."""
from sqlalchemy import select

from app.api.v1.auth import export_my_data
from app.core.rls import reset_rls, set_rls
from app.models import Employer, Offer, Participant
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def test_export_omits_another_participants_offer(db):
    tag = stamp()
    owner = Participant(
        email=f"dbtest-export-a-{tag}@example.com", display_name="Свои",
        password_hash=PASSWORD_HASH, email_verified_at=now(), is_minor=False, is_visible=True,
        specialization="backend", declared_grade="middle", job_search="active", survey_at=now(),
    )
    other = Participant(
        email=f"dbtest-export-b-{tag}@example.com", display_name="Чужие",
        password_hash=PASSWORD_HASH, email_verified_at=now(), is_minor=False, is_visible=True,
        specialization="backend", declared_grade="middle", job_search="active", survey_at=now(),
    )
    company = Employer(
        email=f"dbtest-export-hr-{tag}@example.com", company_name=f"Экспорт {tag}",
        password_hash=PASSWORD_HASH, email_verified_at=now(),
    )
    db.add_all([owner, other, company])
    await db.flush()
    own = Offer(
        employer_id=company.id, candidate_id=owner.id,
        salary_from_gross=100_000, salary_to_gross=120_000, currency="RUB",
        role=f"own-{tag}", work_format="remote", contact_method="почта", status="pending",
    )
    alien = Offer(
        employer_id=company.id, candidate_id=other.id,
        salary_from_gross=100_000, salary_to_gross=120_000, currency="RUB",
        role=f"alien-{tag}", work_format="remote", contact_method="почта", status="pending",
    )
    db.add_all([own, alien])
    await db.commit()
    scope = set_rls(participant_id=str(owner.id))
    try:
        visible = {row.role for row in await db.scalars(select(Offer))}
        assert f"own-{tag}" in visible
        assert f"alien-{tag}" not in visible
        body = await export_my_data({"sub": str(owner.id), "role": "participant"}, db)
        payload = body.body
        text = payload.decode() if isinstance(payload, bytes) else str(payload)
        assert f"own-{tag}" in text
        assert f"alien-{tag}" not in text
    finally:
        reset_rls(scope)
        await wipe_people([owner.id, other.id], [company.id])
