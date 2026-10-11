import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.core.database import Base


class CandidateResume(Base):
    """An extra specialization the candidate looks for work in, beside the one from the survey.

    The grade here is declared. A test passed in the same specialization outranks it.
    """
    __tablename__ = "candidate_resumes"
    __table_args__ = (UniqueConstraint("participant_id", "specialization", name="uq_candidate_resumes_spec"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    specialization = Column(String(30), nullable=False)
    grade = Column(String(20), nullable=False)
    stack = Column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    summary = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
                        onupdate=lambda: datetime.now(UTC))


class SurveyHistory(Base):
    """One row per survey submit: TZ 2.1 «история опроса». The participant row keeps the latest answers."""
    __tablename__ = "survey_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    specialization = Column(String(30), nullable=False)
    industry = Column(String(40))
    work_goal = Column(String(40))
    declared_grade = Column(String(20), nullable=False)
    experience_years = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
