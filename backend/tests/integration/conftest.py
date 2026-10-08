"""Integration tests run against Postgres. They create their own rows and delete them."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.rls import bypass_rls, reset_rls
from app.core.security import hash_password
from app.models import (
    AccessLog,
    CategoryAssignment,
    Consent,
    ConsentLog,
    Employer,
    GradeConfirmation,
    NeedShortlist,
    Offer,
    Participant,
    PracticeAttempt,
    Skill,
    TestSession,
    TestSessionItem,
)
from app.models.profile import DisciplineScore, ProfileEmbedding, ProfileSearchIndex

pytestmark = pytest.mark.db

PASSWORD_HASH = hash_password("dbtest-pass")


def stamp() -> str:
    return uuid.uuid4().hex[:10]


def now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
async def db():
    token = bypass_rls()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
    reset_rls(token)


async def wipe_people(participant_ids: list[uuid.UUID], employer_ids: list[uuid.UUID] | None = None) -> None:
    """Remove rows these tests inserted. Shared item statistics stay: they belong to the bank."""
    participant_ids = [pid for pid in participant_ids if pid is not None]
    employer_ids = [eid for eid in (employer_ids or []) if eid is not None]
    if not participant_ids and not employer_ids:
        return
    token = bypass_rls()
    try:
        async with AsyncSessionLocal() as session:
            if participant_ids:
                session_ids = list(await session.scalars(
                    select(TestSession.id).where(TestSession.participant_id.in_(participant_ids))))
                if session_ids:
                    await session.execute(delete(TestSessionItem).where(
                        TestSessionItem.session_id.in_(session_ids)))
                    await session.execute(delete(TestSession).where(TestSession.id.in_(session_ids)))
                await session.execute(delete(AccessLog).where(AccessLog.participant_id.in_(participant_ids)))
                await session.execute(delete(Offer).where(Offer.candidate_id.in_(participant_ids)))
                await session.execute(delete(NeedShortlist).where(NeedShortlist.participant_id.in_(participant_ids)))
                await session.execute(delete(PracticeAttempt).where(
                    PracticeAttempt.participant_id.in_(participant_ids)))
                await session.execute(delete(GradeConfirmation).where(
                    GradeConfirmation.participant_id.in_(participant_ids)))
                await session.execute(delete(Skill).where(Skill.participant_id.in_(participant_ids)))
                await session.execute(delete(ConsentLog).where(ConsentLog.participant_id.in_(participant_ids)))
                await session.execute(delete(Consent).where(
                    Consent.subject_type == "participant", Consent.subject_id.in_(participant_ids)))
                await session.execute(delete(DisciplineScore).where(
                    DisciplineScore.participant_id.in_(participant_ids)))
                await session.execute(delete(CategoryAssignment).where(
                    CategoryAssignment.participant_id.in_(participant_ids)))
                await session.execute(delete(ProfileEmbedding).where(
                    ProfileEmbedding.participant_id.in_(participant_ids)))
                await session.execute(delete(ProfileSearchIndex).where(
                    ProfileSearchIndex.participant_id.in_(participant_ids)))
                await session.execute(delete(Participant).where(Participant.id.in_(participant_ids)))
            if employer_ids:
                await session.execute(delete(AccessLog).where(AccessLog.employer_id.in_(employer_ids)))
                await session.execute(delete(Offer).where(Offer.employer_id.in_(employer_ids)))
                await session.execute(delete(Consent).where(
                    Consent.subject_type == "employer", Consent.subject_id.in_(employer_ids)))
                await session.execute(delete(Employer).where(Employer.id.in_(employer_ids)))
            await session.commit()
    finally:
        reset_rls(token)
