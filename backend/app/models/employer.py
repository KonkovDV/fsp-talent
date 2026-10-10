import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Employer(Base):
    __tablename__ = "employers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(200), nullable=False)
    email = Column(Text, nullable=False)
    email_bindex = Column(String(64), unique=True)
    password_hash = Column(String(200), nullable=False)
    token_epoch = Column(Integer, nullable=False, default=0, server_default="0")
    # Bumped when a refresh token is exchanged. The new refresh carries the new number.
    refresh_nonce = Column(Integer, nullable=False, default=0, server_default="0")
    email_verified_at = Column(DateTime(timezone=True))
    inn = Column(String(12))
    website = Column(String(200))
    description = Column(Text)
    industry = Column(String(200))
    subscription_tier = Column(String(20), nullable=False, default="free")
    # Set when complaints meet the Wilson rule. Cleared only by `python -m app.services.trust release`.
    invites_paused_at = Column(DateTime(timezone=True))
    # Set only for a demo guest company: sessions close at this moment (services/guest.py).
    guest_until = Column(DateTime(timezone=True))
    # Moderation desk second factor, set only by `python -m app.services.totp enroll`. Sealed with AES-GCM.
    totp_secret = Column(Text)
    totp_last_step = Column(BigInteger)
    totp_verified_at = Column(DateTime(timezone=True))
    # Set only by `python -m app.services.trust partner`. The API cannot write it.
    fsp_partner = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    offers = relationship("Offer", back_populates="employer")
    vacancies = relationship("Vacancy", back_populates="employer")
    access_logs = relationship("AccessLog", back_populates="employer")
