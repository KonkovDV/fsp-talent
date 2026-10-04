import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class VerifiableCredential(Base):
    """W3C VC 2.0 + Ed25519 proof, stored as JSONB.

    proof_value stores the base58-multibase signature string from the DataIntegrityProof
    block (proof.proofValue), mirroring the W3C VC Data Model 2.0 naming.
    """
    __tablename__ = "verifiable_credentials"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False, index=True)
    result_id      = Column(UUID(as_uuid=True), ForeignKey("results.id"), nullable=True)
    credential_json = Column(JSONB, nullable=False)
    proof_value    = Column(String(200), nullable=False)
    issued_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
