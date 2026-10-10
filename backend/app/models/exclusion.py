import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class CandidateBlock(Base):
    """This person asked not to be shown to one company. The row is the pair, not a reason."""
    __tablename__ = "candidate_blocks"
    __table_args__ = (UniqueConstraint("participant_id", "employer_id", name="uq_candidate_blocks"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
