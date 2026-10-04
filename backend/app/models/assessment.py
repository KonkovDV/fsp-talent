"""
Assessment system: IRT-calibrated question bank + test sessions.

Design:
- TestQuestion: question bank entry with IRT parameters (1PL Rasch model)
- TestSession:  per-candidate attempt (one active at a time, expires in 30 min)
- TestAnswer:   individual answers within a session

Grade cooldown: Participant.grade_locked_until prevents re-testing for 90 days
after a grade change.  This column is added in migration 0008.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# How many questions per test session
SESSION_QUESTION_COUNT = 15
# Session expiry (minutes)
SESSION_TTL_MINUTES = 30
# Grade change cooldown (days)
GRADE_COOLDOWN_DAYS = 90


class TestQuestion(Base):
    __tablename__ = "test_questions"
    __table_args__ = (
        CheckConstraint("question_type IN ('mcq', 'open')", name="ck_question_type"),
        CheckConstraint("target_grade IN ('junior', 'middle', 'senior', 'lead')", name="ck_question_grade"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    discipline: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_grade: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    question_type: Mapped[str] = mapped_column(String(10), nullable=False, default="mcq")
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    correct_option: Mapped[str | None] = mapped_column(String(10), nullable=True)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discrimination: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    answers: Mapped[list[TestAnswer]] = relationship("TestAnswer", back_populates="question")


class TestSession(Base):
    __tablename__ = "test_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'expired', 'abandoned')",
            name="ck_session_status",
        ),
        CheckConstraint(
            "target_grade IN ('junior', 'middle', 'senior', 'lead')",
            name="ck_session_grade",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    discipline: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    irt_theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    questions_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    grade_assigned: Mapped[str | None] = mapped_column(String(20), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC) + timedelta(minutes=SESSION_TTL_MINUTES),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answers: Mapped[list[TestAnswer]] = relationship(
        "TestAnswer", back_populates="session", cascade="all, delete-orphan"
    )


class TestAnswer(Base):
    __tablename__ = "test_answers"
    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_answer_session_question"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_questions.id", ondelete="RESTRICT"), nullable=False
    )
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    session: Mapped[TestSession] = relationship("TestSession", back_populates="answers")
    question: Mapped[TestQuestion] = relationship("TestQuestion", back_populates="answers")


GRADE_ORDER = ("junior", "middle", "senior", "lead")
