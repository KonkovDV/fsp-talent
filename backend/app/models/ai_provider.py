import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base
from app.services.field_cipher import open_seal, seal

AI_KINDS = ("gigachat", "yandex", "cloudru", "mws")


class AiProvider(Base):
    """A language model provider from the fixed list in services/ai/providers.py. At most one is active."""
    __tablename__ = "ai_providers"
    __table_args__ = (
        CheckConstraint("kind IN ('gigachat', 'yandex', 'cloudru', 'mws')", name="ck_ai_providers_kind"),
        Index("uq_ai_providers_active", "is_active", unique=True, postgresql_where=text("is_active")),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String(20), nullable=False)
    label = Column(String(80), nullable=False)
    model = Column(String(100), nullable=False)
    check_model = Column(String(100))
    params = Column(JSONB, nullable=False, default=dict)
    secret = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    activated_at = Column(DateTime(timezone=True))


def seal_secret(provider_id: uuid.UUID, plain: str) -> str:
    return seal(str(provider_id), "ai_providers", "secret", plain)


def open_secret(row: AiProvider) -> str:
    return open_seal(str(row.id), "ai_providers", "secret", row.secret)
