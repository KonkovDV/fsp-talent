import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class MethodistLog(Base):
    """Why a methodist released a quarantined item. The row names the item key, not a person."""
    __tablename__ = "methodist_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(40), nullable=False)
    subject = Column(String(80), nullable=False)
    note = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
