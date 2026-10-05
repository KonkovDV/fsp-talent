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
    BigInteger,
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
    # Test v2 (adaptive): see app/services/cat.py
    specialization: Mapped[str | None] = mapped_column(String(30), nullable=True)
    engine: Mapped[str] = mapped_column(String(20), nullable=False, default="fixed_v1")
    p_pass: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_upgrade: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta_se: Mapped[float | None] = mapped_column(Float, nullable=True)
    items_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
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


class TestSessionItem(Base):
    """One served item of an adaptive session. The right answer never leaves the server before the end."""
    __tablename__ = "test_session_items"
    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_session_item_seq"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    item_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    family_id: Mapped[str] = mapped_column(String(40), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    topic: Mapped[str] = mapped_column(String(30), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    options: Mapped[list] = mapped_column(JSONB, nullable=False)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    a: Mapped[float] = mapped_column(Float, nullable=False)
    b: Mapped[float] = mapped_column(Float, nullable=False)
    c: Mapped[float] = mapped_column(Float, nullable=False)
    time_limit_s: Mapped[int] = mapped_column(Integer, nullable=False)
    served_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                default=lambda: datetime.now(UTC))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answer_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    timed_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ItemStat(Base):
    """Per item key: answers, model-expected answers (for leak drift) and calibration offset."""
    __tablename__ = "item_stats"

    item_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(40), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    n: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expected: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    variance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    b_offset: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    z: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=lambda: datetime.now(UTC))


class GradeConfirmation(Base):
    """Grade confirmed by a test for one specialization. Never lowered by a later test."""
    __tablename__ = "grade_confirmations"
    __table_args__ = (UniqueConstraint("participant_id", "specialization", name="uq_grade_confirmation_spec"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    specialization: Mapped[str] = mapped_column(String(30), nullable=False)
    grade: Mapped[str] = mapped_column(String(20), nullable=False)
    p_pass: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    se: Mapped[float | None] = mapped_column(Float, nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                   default=lambda: datetime.now(UTC))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PracticeAttempt(Base):
    """One short task from a vacancy or the specialization plan. It does not change the grade."""
    __tablename__ = "practice_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True)
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    topic: Mapped[str] = mapped_column(String(40), nullable=False)
    family_id: Mapped[str] = mapped_column(String(40), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    options: Mapped[list] = mapped_column(JSONB, nullable=False)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=lambda: datetime.now(UTC))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
