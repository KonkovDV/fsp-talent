"""A meeting after the candidate has accepted an invitation.

The employer offers one to three times. The candidate picks one. Both sides download
the same calendar file. The outcome later changes how likely this candidate is to
accept the next invitation from the same company.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

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
