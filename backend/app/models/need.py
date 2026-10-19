import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class Need(Base):
    """An employer's search profile. `version` points at the current NeedVersion."""
    __tablename__ = "needs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id", ondelete="CASCADE"), nullable=False,
                         index=True)
    title = Column(String(200), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class NeedVersion(Base):
    __tablename__ = "need_versions"
    __table_args__ = (UniqueConstraint("need_id", "version", name="uq_need_version"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    need_id = Column(UUID(as_uuid=True), ForeignKey("needs.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    params = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class NeedShortlist(Base):
    __tablename__ = "need_shortlist"
    __table_args__ = (UniqueConstraint("need_id", "participant_id", name="uq_need_shortlist"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    need_id = Column(UUID(as_uuid=True), ForeignKey("needs.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    score = Column(Float)
    status = Column(String(20), nullable=False, default="shortlisted")
    note = Column(String(500))
    added_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class GuestReview(Base):
    """A time-limited link to an anonymized shortlist. The token itself is not stored."""

    __tablename__ = "guest_reviews"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id", ondelete="CASCADE"), nullable=False)
    need_id = Column(UUID(as_uuid=True), ForeignKey("needs.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    title = Column(String(200), nullable=False)
    seats = Column(JSONB, nullable=False)
    seat_ids = Column(JSONB, nullable=False)
    marks = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime(timezone=True), nullable=False)


class NeedHidden(Base):
    """A card this company hid from one need. The row stays when the need gets a new version."""
    __tablename__ = "need_hidden"
    __table_args__ = (UniqueConstraint("need_id", "participant_id", name="uq_need_hidden"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    need_id = Column(UUID(as_uuid=True), ForeignKey("needs.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    hidden_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
