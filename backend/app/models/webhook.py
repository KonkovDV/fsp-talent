import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class WebhookEndpoint(Base):
    """Where a company receives hiring events. The secret is sealed and is not a contact."""
    __tablename__ = "webhook_endpoints"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id", ondelete="CASCADE"), nullable=False)
    url = Column(Text, nullable=False)
    secret = Column(Text, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class WebhookDelivery(Base):
    """One attempt series for one event. The id is the webhook-id the receiver uses to drop duplicates."""
    __tablename__ = "webhook_deliveries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id = Column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(40), nullable=False)
    payload = Column(Text, nullable=False)
    attempt = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    next_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    last_code = Column(Integer)
    last_error = Column(String(300))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
