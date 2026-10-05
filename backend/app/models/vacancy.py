import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Vacancy(Base):
    """A published job. Matching against a candidate profile is the direct case requirement."""
    __tablename__ = "vacancies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(4000))
    role = Column(String(50))
    grade = Column(String(20))
    discipline = Column(String(50))
    min_rank = Column(String(10))
    skills = Column(JSONB, nullable=False, default=list)
    salary_from_gross = Column(Integer)
    salary_to_gross = Column(Integer)
    work_format = Column(String(20), nullable=False, default="remote")
    allows_minors = Column(Boolean, nullable=False, default=False)
    is_open = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    employer = relationship("Employer", back_populates="vacancies")
    applications = relationship("Application", back_populates="vacancy")


class Application(Base):
    """Candidate applied to a vacancy. That application is their consent to share contacts."""
    __tablename__ = "applications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vacancy_id = Column(UUID(as_uuid=True), ForeignKey("vacancies.id"), nullable=False, index=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="applied")
    viewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    vacancy = relationship("Vacancy", back_populates="applications")
    candidate = relationship("Participant", back_populates="applications")
    __table_args__ = (UniqueConstraint("vacancy_id", "candidate_id", name="uq_application_pair"),)
