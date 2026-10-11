"""Personal data lifecycle for candidates (152-FZ).

Contacts go to an employer only while the candidate's consent to processing (pd_candidate) is in force.
Withdrawing it hides the card at once; 30 days later the identifying fields are erased (part 5 of article 21).
Deleting the account erases them immediately. Sport results stay as anonymous rows: they belong to the
federation's protocol, and without name, e-mail, phone, FSP id and birth date they no longer identify anyone.
The consent and access logs stay: they are the proof that processing was lawful.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Application,
    CandidateResume,
    CategoryAssignment,
    Consent,
    ConsentLog,
    NeedShortlist,
    Offer,
    OfferMessage,
    Participant,
    ProfileEmbedding,
    ProfileSearchIndex,
    Skill,
    SurveyHistory,
    TaskSubmission,
)
from app.services.identity import active_consent
from app.services.search.cache import bump_bank_epoch

RETENTION_AFTER_WITHDRAWAL = timedelta(days=30)


async def contacts_allowed(db: AsyncSession, participant: Participant) -> bool:
    """True while the candidate is not erased and the processing consent is in force."""
    if participant.deleted_at is not None:
        return False
    return await active_consent(db, "participant", participant.id, "pd_candidate") is not None


async def erase_participant(db: AsyncSession, participant: Participant, reason: str) -> None:
    """Remove everything that identifies the person. Idempotent."""
    now = datetime.now(UTC)
    if participant.deleted_at is None:
        participant.deleted_at = now
    for field in ("display_name", "email", "password_hash", "email_verified_at", "telegram", "phone",
                  "birth_date", "fsp_id", "fsp_linked_at", "region", "industry",
                  "guardian_email", "guardian_consent_at"):
        setattr(participant, field, None)
    participant.is_visible = False
    participant.public_profile = False
    participant.token_epoch = (participant.token_epoch or 0) + 1
    pid = participant.id
    await db.execute(delete(Skill).where(Skill.participant_id == pid))
    await db.execute(delete(CandidateResume).where(CandidateResume.participant_id == pid))
    await db.execute(delete(SurveyHistory).where(SurveyHistory.participant_id == pid))
    await db.execute(delete(ProfileEmbedding).where(ProfileEmbedding.participant_id == pid))
    await db.execute(delete(ProfileSearchIndex).where(ProfileSearchIndex.participant_id == pid))
    await db.execute(delete(CategoryAssignment).where(CategoryAssignment.participant_id == pid))
    await db.execute(delete(NeedShortlist).where(NeedShortlist.participant_id == pid))
    await db.execute(update(Offer).where(Offer.candidate_id == pid, Offer.status == "pending")
                     .values(status="withdrawn"))
    await db.execute(update(Application).where(Application.candidate_id == pid,
                                               Application.status.in_(("applied", "reviewing", "invited")))
                     .values(status="closed"))
    await db.execute(update(Consent).where(Consent.subject_type == "participant", Consent.subject_id == pid,
                                           Consent.withdrawn_at.is_(None)).values(withdrawn_at=now))
    # Free text the person wrote can identify them: task answers and messages go, verdicts stay anonymous.
    await db.execute(update(TaskSubmission).where(TaskSubmission.participant_id == pid)
                     .values(answer_text=None, comment=None))
    await db.execute(delete(OfferMessage).where(
        OfferMessage.author_role == "participant",
        OfferMessage.offer_id.in_(select(Offer.id).where(Offer.candidate_id == pid))))
    participant.employer_task_title = None
    participant.employer_task_passed = None
    participant.employer_task_at = None
    db.add(ConsentLog(participant_id=pid, event_type="erased", actor_id=pid, meta={"reason": reason}))
    await db.flush()
    await bump_bank_epoch()


async def due_for_erasure(db: AsyncSession, now: datetime | None = None) -> list[uuid.UUID]:
    """Candidates whose pd_candidate consent was withdrawn more than 30 days ago and never given again."""
    now = now or datetime.now(UTC)
    withdrawn = (select(Consent.subject_id)
                 .where(Consent.subject_type == "participant", Consent.kind == "pd_candidate",
                        Consent.withdrawn_at < now - RETENTION_AFTER_WITHDRAWAL))
    active = (select(Consent.subject_id)
              .where(Consent.subject_type == "participant", Consent.kind == "pd_candidate",
                     Consent.withdrawn_at.is_(None)))
    rows = await db.scalars(select(Participant.id).where(
        Participant.id.in_(withdrawn), Participant.id.not_in(active), Participant.deleted_at.is_(None)))
    return list(rows)


async def purge_withdrawn(db: AsyncSession, now: datetime | None = None) -> int:
    ids = await due_for_erasure(db, now)
    for pid in ids:
        participant = await db.get(Participant, pid)
        if participant is not None:
            await erase_participant(db, participant, reason="consent_withdrawn_30d")
    return len(ids)
