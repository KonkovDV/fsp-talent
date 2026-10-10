import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

FAVORITES_MAX = 200


class EmployerFavorite(Base):
    """A company's bookmark on an anonymous card, apart from any need. Only that company sees it."""
    __tablename__ = "employer_favorites"
    __table_args__ = (UniqueConstraint("employer_id", "participant_id", name="uq_employer_favorites_pair"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
