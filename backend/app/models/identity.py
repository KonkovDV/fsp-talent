import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class EmailVerification(Base):
    """One-time code + link token for email confirmation and password reset. Only hashes are stored."""
    __tablename__ = "email_verifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_type = Column(String(20), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    purpose = Column(String(20), nullable=False)
    email = Column(Text, nullable=False)
    email_bindex = Column(String(64), index=True)
    code_hash = Column(String(64), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class Consent(Base):
    """A person's consent to one exact version of a legal document (version + SHA-256 of its text).

    Withdrawal sets withdrawn_at; the row is never deleted, so the history stays provable.
    """
    __tablename__ = "consents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_type = Column(String(20), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    kind = Column(String(40), nullable=False)
    version = Column(String(20), nullable=False)
    sha256 = Column(String(64), nullable=False)
    given_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    withdrawn_at = Column(DateTime(timezone=True))
    ip_hash = Column(String(64))
    user_agent = Column(String(300))
