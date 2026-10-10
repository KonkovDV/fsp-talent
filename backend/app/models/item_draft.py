import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

DRAFT_STATUSES = ("pending", "approved", "rejected")


class ItemDraft(Base):
    """A model-written item that two models agreed on. A person reviews it; the test never serves it."""
    __tablename__ = "item_drafts"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_item_drafts_status"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spec = Column(String(30), nullable=False)
    topic = Column(String(40), nullable=False)
    level = Column(Integer, nullable=False)
    stem = Column(Text, nullable=False)
    key = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
