import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class ConsentLog(Base):
    """Append-only -- 152-FZ audit trail. Never UPDATE or DELETE."""
    __tablename__ = "consent_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    ip_hash = Column(String(64))
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    meta = Column(JSONB, nullable=False, default=dict)
    participant = relationship("Participant", back_populates="consent_logs")


class AccessLog(Base):
    __tablename__ = "access_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False)
    access_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    employer = relationship("Employer", back_populates="access_logs")
