"""Return the jury stand to the state the three-minute show starts from.

Passwords of the published accounts go back to the printed one, jury surveys and tests
are cleared, and the show invitations are pending again. Refuses outside the demo stand.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.demo_guard import is_protected
from app.core.security import hash_password
from app.legal import documents
from app.models import (
    CategoryAssignment,
    Complaint,
    Consent,
    Employer,
    GradeConfirmation,
    Offer,
    Participant,
    PracticeAttempt,
    ProfileSearchIndex,
    Skill,
    TestSession,
)
from app.services.identity import active_consent
from seed.demo_activity import restore_pending_invites
from seed.generate_seed import DEMO_PASSWORD, JURY_BIRTH


def refuse_outside_demo() -> None:
    if os.environ.get("ENV", "").lower() == "production":
        raise SystemExit("Сброс демо-стенда не выполняется, когда ENV=production")
    if not settings.DEMO_MODE:
        raise SystemExit("Сброс демо-стенда выполняется только при DEMO_MODE")


async def _clear_jury(db, person: Participant) -> None:
    pid = person.id
    offer_ids = list(await db.scalars(select(Offer.id).where(Offer.candidate_id == pid)))
    if offer_ids:
        await db.execute(delete(Complaint).where(Complaint.offer_id.in_(offer_ids)))
        await db.execute(delete(Offer).where(Offer.id.in_(offer_ids)))
    session_ids = list(await db.scalars(select(TestSession.id).where(TestSession.participant_id == pid)))
    if session_ids:
        await db.execute(delete(TestSession).where(TestSession.id.in_(session_ids)))
    await db.execute(delete(GradeConfirmation).where(GradeConfirmation.participant_id == pid))
    await db.execute(delete(PracticeAttempt).where(PracticeAttempt.participant_id == pid))
    await db.execute(delete(Skill).where(Skill.participant_id == pid))
    await db.execute(delete(CategoryAssignment).where(CategoryAssignment.participant_id == pid))
    await db.execute(delete(ProfileSearchIndex).where(ProfileSearchIndex.participant_id == pid))
    person.survey_at = None
    person.specialization = None
    person.declared_grade = None
    person.assessed_grade = None
    person.assessed_at = None
    person.grade_locked_until = None
    person.industry = None
    person.work_goal = None
    person.salary_from_gross = None
    person.salary_to_gross = None
    person.experience_years = None


async def _restore_consents(db, person: Participant, now: datetime) -> None:
    for doc in documents().values():
        if not doc.required or "participant" not in doc.roles:
            continue
        if await active_consent(db, "participant", person.id, doc.kind) is not None:
            continue
        db.add(Consent(subject_type="participant", subject_id=person.id, kind=doc.kind,
                       version=doc.version, sha256=doc.sha256, given_at=now))


async def reset_demo() -> None:
    refuse_outside_demo()
    from app.core.rls import bypass_rls
    bypass_rls()
    password_hash = hash_password(DEMO_PASSWORD)
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        people = list(await db.scalars(select(Participant).where(Participant.email.is_not(None))))
        jury = 0
        for person in people:
            if not is_protected(person.email):
                continue
            person.password_hash = password_hash
            person.token_epoch = int(person.token_epoch or 0) + 1
            person.refresh_nonce = int(person.refresh_nonce or 0) + 1
            await _restore_consents(db, person, now)
            if (person.email or "").startswith("jury") and person.email.endswith("@demo.talent"):
                if person.birth_date is None:
                    person.birth_date = JURY_BIRTH
                    person.is_minor = False
                await _clear_jury(db, person)
                jury += 1
        companies = 0
        for company in await db.scalars(select(Employer).where(Employer.email.is_not(None))):
            if not is_protected(company.email):
                continue
            company.password_hash = password_hash
            company.token_epoch = int(company.token_epoch or 0) + 1
            company.refresh_nonce = int(company.refresh_nonce or 0) + 1
            company.invites_paused_at = None
            companies += 1
        invites = await restore_pending_invites(db)
        await db.commit()
        # jury6…jury10 come back ready (survey and a confirmed grade); jury1…jury5 stay empty for the show.
        from seed.demo_ready import make_ready
        ready = await make_ready(db)
        print(f"demo reset jury={jury} companies={companies} invites={invites} ready={ready['ready']}")


def main() -> None:
    asyncio.run(reset_demo())


if __name__ == "__main__":
    main()
