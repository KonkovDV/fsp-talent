import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Notification(Base):
    """An event the other side of a hiring step should see: invitation, answer, application, status."""
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_recipient", "recipient_role", "recipient_id", "read_at"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_role = Column(String(20), nullable=False)   # participant | employer
    recipient_id = Column(UUID(as_uuid=True), nullable=False)
    kind = Column(String(40), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text)
    link = Column(String(200))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    read_at = Column(DateTime(timezone=True))
