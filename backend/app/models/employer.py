import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class Employer(Base):
    __tablename__ = "employers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    inn = Column(String(12))
    website = Column(String(200))
    subscription_tier = Column(String(20), nullable=False, default="free")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    offers = relationship("Offer", back_populates="employer")
    access_logs = relationship("AccessLog", back_populates="employer")
