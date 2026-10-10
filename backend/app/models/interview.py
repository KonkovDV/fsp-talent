"""A meeting after the candidate has accepted an invitation.

The employer offers one to three times. The candidate picks one. Both sides download
the same calendar file. The outcome later changes how likely this candidate is to
accept the next invitation from the same company.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base

FORMATS = ("online", "office", "phone")
OUTCOMES = ("passed", "failed", "no_show")


class InterviewSlot(Base):
    __tablename__ = "interview_slots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    format = Column(String(20), nullable=False)
    place = Column(Text)
    chosen = Column(Boolean, nullable=False, default=False)
    outcome = Column(String(20))
    outcome_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class InterviewCode(Base):
    """A coding step on an accepted invitation. Snapshots are drafts, not a grade."""
    __tablename__ = "interview_code"
    __table_args__ = (UniqueConstraint("offer_id", name="uq_interview_code_offer"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id", ondelete="CASCADE"), nullable=False)
    problem_id = Column(String(40))
    prompt = Column(Text, nullable=False, default="")
    draft = Column(Text, nullable=False, default="")
    draft_version = Column(Integer, nullable=False, default=0, server_default="0")
    snapshots = Column(JSONB, nullable=False, default=list, server_default="[]")
    dispute = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
