import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Offer(Base):
    __tablename__ = "offers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False)
    salary_from_gross = Column(Integer, nullable=False)
    salary_to_gross = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="RUB")
    role = Column(String(100), nullable=False)
    work_format = Column(String(20), nullable=False)
    message = Column(Text)
    # TZ 2.2 п.2: the invitation carries the way to reach the company. Nullable only for rows created
    # before migration 0010; the API requires it for every new offer.
    contact_method = Column(String(300))
    status = Column(String(20), nullable=False, default="pending")
    # Optional, set when the candidate declines: salary, format, stack, not_looking, other.
    decline_reason = Column(String(20))
    # When the candidate accepted or declined (migration 0002). A decline pauses new invitations for 30 days.
    responded_at = Column(DateTime(timezone=True))
    contacts_revealed_at = Column(DateTime(timezone=True))
    # The candidate closed the contacts for this company after accepting. Other companies are not affected.
    contacts_revoked_at = Column(DateTime(timezone=True))
    employer_viewed_at = Column(DateTime(timezone=True))
    # TZ 2.2 п.3: "просмотрено" — first time the candidate opened the list with this pending offer.
    candidate_viewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(UTC) + timedelta(days=14))
    employer = relationship("Employer", back_populates="offers")
    candidate = relationship("Participant", back_populates="offers", foreign_keys=[candidate_id])


class OfferMessage(Base):
    """A message in the thread of an accepted invitation. Either side writes; the other reads."""
    __tablename__ = "offer_messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True)
    author_role = Column(String(20), nullable=False)   # participant | employer
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    read_at = Column(DateTime(timezone=True))
