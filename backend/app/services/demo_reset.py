"""Clear one jury account on the demo stand.

Used by the nightly reset and by the juror's own «Начать заново» button, so a second
expert on jury1 does not see the previous expert's survey, test or grade cooldown.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, select

from app.legal import documents
from app.models import (
    CategoryAssignment,
    Complaint,
    Consent,
    GradeConfirmation,
    Offer,
    Participant,
    PracticeAttempt,
    ProfileSearchIndex,
    Skill,
    TestSession,
)
from app.services.identity import active_consent

# Same date as seed.generate_seed.JURY_BIRTH; the app does not import the seed package.
JURY_BIRTH = date(1990, 6, 15)


def is_jury(email: str | None) -> bool:
    """jury1..jury10@demo.talent only; other demo and real accounts are not jury."""
    from app.core.demo_guard import PUBLISHED_EMAILS
    e = (email or "").strip().lower()
    return e.startswith("jury") and e.endswith("@demo.talent") and e in PUBLISHED_EMAILS


async def clear_jury(db, person: Participant) -> None:
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


async def restore_consents(db, person: Participant, now: datetime) -> None:
    for doc in documents().values():
        if not doc.required or "participant" not in doc.roles:
            continue
        if await active_consent(db, "participant", person.id, doc.kind) is not None:
            continue
        db.add(Consent(subject_type="participant", subject_id=person.id, kind=doc.kind,
                       version=doc.version, sha256=doc.sha256, given_at=now))
