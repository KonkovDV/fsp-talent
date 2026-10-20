"""A candidate's action reaches the company's ATS even though row-level security hides its endpoints."""
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.core.rls import reset_rls, set_rls
from app.models import Employer, Participant
from app.models.webhook import WebhookDelivery, WebhookEndpoint
from app.services.webhooks import enqueue
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def test_the_candidate_scope_queues_the_company_event_and_keeps_its_own_scope(db):
    tag = stamp()
    person = Participant(email=f"dbtest-hook-{tag}@example.com", display_name="Вебхук",
                         password_hash=PASSWORD_HASH, email_verified_at=now(), is_minor=False)
    company = Employer(email=f"dbtest-hook-hr-{tag}@example.com", company_name=f"Вебхук {tag}",
                       password_hash=PASSWORD_HASH, email_verified_at=now())
    db.add(person)
    db.add(company)
    await db.flush()
    endpoint = WebhookEndpoint(employer_id=company.id, url="https://ats.example.com/hook",
                               secret="sealed", active=True)
    db.add(endpoint)
    await db.commit()
    try:
        scope = set_rls(participant_id=str(person.id))
        try:
            async with AsyncSessionLocal() as session:
                hidden = list(await session.scalars(select(WebhookEndpoint.id).where(
                    WebhookEndpoint.employer_id == company.id)))
                assert hidden == [], "the candidate scope must not read the company's endpoints"
                queued = await enqueue(session, company.id, "contacts.revoked",
                                       {"candidate": {"ref": "c_test", "delete": True}})
                assert queued == 1
                assert await session.scalar(text("SELECT current_setting('app.bypass_rls', true)")) in ("", None)
                assert list(await session.scalars(select(WebhookEndpoint.id).where(
                    WebhookEndpoint.employer_id == company.id))) == []
                await session.commit()
        finally:
            reset_rls(scope)
        rows = list(await db.scalars(select(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint.id)))
        assert [row.event_type for row in rows] == ["contacts.revoked"]
    finally:
        await wipe_people([person.id], [company.id])
