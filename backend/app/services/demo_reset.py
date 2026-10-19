"""Clear one jury account on the demo stand.

Used by the nightly reset and by the juror's own «Начать заново» button, so a second
expert on jury1 does not see the previous expert's survey, test or grade cooldown.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, select, text

from app.legal import documents
from app.models import (
    Application,
    CandidateInterest,
    CandidateResume,
    CategoryAssignment,
    Complaint,
    Consent,
    EmployerFavorite,
    GradeConfirmation,
    Offer,
    Participant,
    PracticeAttempt,
    ProfileSearchIndex,
    Skill,
    TestSession,
    VerifiableCredential,
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
    # RT-08: everything a juror produced, so the next expert does not inherit it.
    await db.execute(delete(VerifiableCredential).where(VerifiableCredential.participant_id == pid))
    await db.execute(delete(Application).where(Application.candidate_id == pid))
    await db.execute(delete(Complaint).where(Complaint.participant_id == pid))
    await db.execute(delete(CandidateResume).where(CandidateResume.participant_id == pid))
    await db.execute(delete(EmployerFavorite).where(EmployerFavorite.participant_id == pid))
    await db.execute(delete(CandidateInterest).where(CandidateInterest.participant_id == pid))
    # survey_history arrives with revision 0002 (#297); the reset works with or without it.
    if await db.scalar(text("SELECT to_regclass('public.survey_history') IS NOT NULL")):
        await db.execute(text("DELETE FROM public.survey_history WHERE participant_id = :pid"), {"pid": pid})
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
    clear_personal(person)


def juror_name(email: str | None) -> str:
    """The seed name of jury{n}@demo.talent, «Член жюри n»."""
    local = (email or "").split("@", 1)[0]
    number = local[len("jury"):] if local.startswith("jury") else ""
    return f"Член жюри {number}" if number.isdigit() else "Член жюри"


def clear_personal(person: Participant) -> None:
    """PR295-01: what the previous expert typed about themselves goes too — name, contacts, region,
    preferences and the public page. The next expert on the same login starts from the seed state."""
    person.display_name = juror_name(person.email)
    person.phone = None
    person.telegram = None
    person.github = None
    person.region = None
    person.relocation = False
    person.soft_skills = []
    person.work_formats = []
    person.excluded_industries = []
    person.certificate_grade = None
    person.category_opened_at = None
    person.practice_topic = person.practice_ok = person.practice_at = None
    person.employer_task_title = person.employer_task_passed = person.employer_task_at = None
    person.public_profile = False
    person.show_city = person.show_stack = person.show_fsp = person.show_experience = True
    person.job_search = "open"


async def restore_consents(db, person: Participant, now: datetime) -> None:
    for doc in documents().values():
        if not doc.required or "participant" not in doc.roles:
            continue
        if await active_consent(db, "participant", person.id, doc.kind) is not None:
            continue
        db.add(Consent(subject_type="participant", subject_id=person.id, kind=doc.kind,
                       version=doc.version, sha256=doc.sha256, given_at=now))
