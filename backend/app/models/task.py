"""Tasks an employer writes for candidates (TZ 2.1, regular tasks).

A task with a reference answer (a number or one of the options) is checked by the system. An open task
(a script, a business decision) is checked by the employer who wrote it. A task is either public, for all
candidates of one specialization, or addressed to one candidate found in search.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class EmployerTask(Base):
    __tablename__ = "employer_tasks"
    __table_args__ = (
        Index("ix_employer_tasks_public", "visibility", "specialization", "is_open"),
        Index("ix_employer_tasks_candidate", "candidate_id"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id = Column(UUID(as_uuid=True), ForeignKey("employers.id", ondelete="CASCADE"), nullable=False,
                         index=True)
    vacancy_id = Column(UUID(as_uuid=True), ForeignKey("vacancies.id", ondelete="SET NULL"))
    title = Column(String(200), nullable=False)
    statement = Column(Text, nullable=False)
    answer_type = Column(String(10), nullable=False)          # number | choice | open | code
    options = Column(JSONB, nullable=False, default=list)      # choice only
    correct_index = Column(Integer)                            # choice only; never sent before the answer
    reference_number = Column(String(40))                      # number key or lab id; never sent before the answer
    visibility = Column(String(10), nullable=False)            # public | addressed
    specialization = Column(String(30))                        # public: who sees it
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"))
    deadline = Column(DateTime(timezone=True))
    is_open = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class TaskSubmission(Base):
    """One answer of one candidate to one task. status: checked (by the system) | review | reviewed."""
    __tablename__ = "task_submissions"
    __table_args__ = (UniqueConstraint("task_id", "participant_id", name="uq_task_submission"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("employer_tasks.id", ondelete="CASCADE"), nullable=False,
                     index=True)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False,
                            index=True)
    answer_text = Column(Text)
    answer_index = Column(Integer)
    status = Column(String(10), nullable=False)
    passed = Column(Boolean)
    comment = Column(String(1000))
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    reviewed_at = Column(DateTime(timezone=True))
