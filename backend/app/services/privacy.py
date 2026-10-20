"""Personal data lifecycle for candidates (152-FZ).

Contacts go to an employer only while the candidate's consent to processing (pd_candidate) is in force.
Withdrawing it hides the card at once; 30 days later the identifying fields are erased (part 5 of article 21).
Deleting the account erases them immediately. Sport rows stay for the federation aggregate, but the
registry event id, the event title, the protocol link and the raw payload are cleared: those fields
are direct links back to a named protocol. Place, date and discipline can still be quasi-identifiers.
The consent and access logs stay: they are the proof that processing was lawful.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Integer, String, cast, delete, extract, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AccessLog,
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
    Result,
    Skill,
    SurveyHistory,
    TaskSubmission,
    VerifiableCredential,
)
from app.models.assessment import GradeDispute
from app.services.identity import active_consent
from app.services.search.cache import bump_bank_epoch

RETENTION_AFTER_WITHDRAWAL = timedelta(days=30)


def _without_stored_identity(document: object) -> dict:
    """Drop the subject id and the event title from a stored credential. The signature no longer matches,
    and the row is revoked in the same step."""
    if not isinstance(document, dict):
        return {}
    subject = document.get("credentialSubject")
    if not isinstance(subject, dict):
        return {k: v for k, v in document.items() if k != "credentialSubject"}
    cleaned = {k: v for k, v in subject.items() if k != "id"}
    achievement = cleaned.get("achievement")
    if isinstance(achievement, dict):
        cleaned["achievement"] = {
            k: v for k, v in achievement.items() if k not in {"eventName", "eventId", "name"}
        }
    return {**document, "credentialSubject": cleaned}


async def contacts_allowed(db: AsyncSession, participant: Participant) -> bool:
    """True while the candidate is not erased and the processing consent is in force."""
    if participant.deleted_at is not None:
        return False
    return await active_consent(db, "participant", participant.id, "pd_candidate") is not None


async def tell_contact_holders(db: AsyncSession, participant_id: uuid.UUID, reason: str) -> int:
    """Every company that received the contacts gets `contacts.revoked` with `delete: true`.

    A company counts when an accepted invitation still has open contacts, or when it opened contacts
    through a vacancy application or an accepted invitation (access log). Accepted invitations are
    closed here so a later re-consent does not silently reopen the old shares. Pending ATS deliveries
    that still carry contacts are marked superseded before the revoke event is queued. A repeat event
    is harmless: deleting twice leaves the same state. The caller commits.
    """
    from app.services.field_cipher import public_ref
    from app.services.webhooks import drop_stale_contact_deliveries, enqueue

    offer_holders = set(await db.scalars(select(Offer.employer_id).where(
        Offer.candidate_id == participant_id, Offer.status == "accepted",
        Offer.contacts_revoked_at.is_(None)).distinct()))
    log_holders = set(await db.scalars(select(AccessLog.employer_id).where(
        AccessLog.participant_id == participant_id,
        AccessLog.access_type.in_(("application_contacts", "contacts_view"))).distinct()))
    holders = sorted(offer_holders | log_holders, key=str)
    closed_at = datetime.now(UTC)
    await db.execute(update(Offer).where(
        Offer.candidate_id == participant_id, Offer.status == "accepted",
        Offer.contacts_revoked_at.is_(None)).values(contacts_revoked_at=closed_at))
    now = closed_at.isoformat()
    ref = public_ref(participant_id)
    for employer_id in holders:
        await drop_stale_contact_deliveries(db, employer_id, ref)
        await enqueue(db, employer_id, "contacts.revoked", {
            "created_at": now, "employer_id": str(employer_id),
            "candidate": {"ref": ref, "delete": True},
            "reason": reason,
        })
    return len(holders)


async def erase_participant(db: AsyncSession, participant: Participant, reason: str) -> None:
    """Remove everything that identifies the person. Idempotent."""
    now = datetime.now(UTC)
    if participant.deleted_at is None:
        participant.deleted_at = now
    await tell_contact_holders(db, participant.id, reason)
    for field in ("display_name", "email", "email_bindex", "password_hash", "email_verified_at",
                  "telegram", "phone", "github", "birth_date", "fsp_id", "fsp_linked_at", "region",
                  "industry", "guardian_email", "guardian_consent_at"):
        setattr(participant, field, None)
    participant.guardian_link_generation = int(participant.guardian_link_generation or 0) + 1
    participant.relocation = False
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
    # Free text the person wrote can identify them: task answers, messages and dispute notes go.
    await db.execute(update(TaskSubmission).where(TaskSubmission.participant_id == pid)
                     .values(answer_text=None, comment=None))
    await db.execute(delete(OfferMessage).where(
        OfferMessage.author_role == "participant",
        OfferMessage.offer_id.in_(select(Offer.id).where(Offer.candidate_id == pid))))
    await db.execute(update(GradeDispute).where(GradeDispute.participant_id == pid).values(
        reason=None, decision_note=None))
    await db.execute(update(GradeDispute).where(
        GradeDispute.participant_id == pid, GradeDispute.status == "open").values(
        status="upheld", decided_at=now, decision_note=None))
    participant.employer_task_title = None
    participant.employer_task_passed = None
    participant.employer_task_at = None
    await db.execute(update(Result).where(Result.participant_id == pid).values(
        event_id=cast(Result.id, String),
        event_name="Обезличенный протокол",
        protocol_url=None,
        raw_data={},
        regions_count=None,
        event_date=func.make_date(cast(extract("year", Result.event_date), Integer), 1, 1),
    ))
    for vc in await db.scalars(select(VerifiableCredential).where(VerifiableCredential.participant_id == pid)):
        vc.revoked_at = vc.revoked_at or now
        vc.credential_json = _without_stored_identity(vc.credential_json)
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
