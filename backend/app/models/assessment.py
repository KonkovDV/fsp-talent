"""Adaptive grade test: sessions, served items, confirmed grades, item statistics and practice tasks.

There is no stored question bank. Every item is generated from a parametric family (app/items) when it is
served, and the key is computed by code; see app/services/cat.py for the IRT 3PL item selection.

- TestSession:       one attempt of a candidate (one active at a time)
- TestSessionItem:   an item served in that attempt; its key never leaves the server before the end
- GradeConfirmation: a grade confirmed by the test, per specialization
- ItemStat:          per-key answer statistics for leak detection (app/services/item_monitor.py)
- PracticeAttempt:   a short task that does not change the grade

A grade change starts the cooldown (GRADE_COOLDOWN_DAYS) for that specialization.
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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Grade change cooldown (days)
GRADE_COOLDOWN_DAYS = 90
# An unfinished attempt expires after this many minutes
SESSION_TTL_MINUTES = 40


class TestSession(Base):
    __tablename__ = "test_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'expired', 'abandoned')",
            name="ck_session_status",
        ),
        CheckConstraint(
            "target_grade IN ('intern', 'junior', 'middle', 'senior', 'lead')",
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
    engine: Mapped[str] = mapped_column(String(20), nullable=False, default="cat_v2")
    p_pass: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_upgrade: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta_se: Mapped[float | None] = mapped_column(Float, nullable=True)
    items_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


GRADE_ORDER = ("intern", "junior", "middle", "senior", "lead")


class GradeDispute(Base):
    """A request to look at a finished test again. It does not change the grade."""
    __tablename__ = "grade_disputes"
    __table_args__ = (UniqueConstraint("session_id", name="uq_grade_dispute_session"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


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
    # A whole-number answer is typed (app.items.typed_answer): the options stay on the server.
    typed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answer_text: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # HMAC of the served key. A row whose index no longer matches this mac is not scored.
    answer_mac: Mapped[str | None] = mapped_column(String(64), nullable=True)


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
    cusum: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
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
