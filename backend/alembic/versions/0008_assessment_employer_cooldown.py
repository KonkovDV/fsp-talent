"""Assessment tables, employer description/industry, participant grade cooldown.

Revision ID: 0008
Revises: 0007_result_participant_event
Create Date: 2026-10-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007_result_participant_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. pg_trgm extension (needed for GIN trgm indexes on search)
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ------------------------------------------------------------------
    # 2. Employer: add description + industry columns
    # ------------------------------------------------------------------
    op.add_column("employers", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("employers", sa.Column("industry", sa.String(200), nullable=True))

    # ------------------------------------------------------------------
    # 3. Participants: add grade_locked_until column (grade change cooldown)
    # ------------------------------------------------------------------
    op.add_column(
        "participants",
        sa.Column("grade_locked_until", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # 4. test_questions table
    # ------------------------------------------------------------------
    op.create_table(
        "test_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("discipline", sa.String(80), nullable=False),
        sa.Column("target_grade", sa.String(20), nullable=False),
        sa.Column("question_type", sa.String(10), nullable=False, server_default="mcq"),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("correct_option", sa.String(10), nullable=True),
        sa.Column("difficulty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("discrimination", sa.Float(), nullable=False, server_default="1"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "question_type IN ('mcq', 'open')", name="ck_question_type"
        ),
        sa.CheckConstraint(
            "target_grade IN ('junior', 'middle', 'senior', 'lead')",
            name="ck_question_grade",
        ),
    )
    op.create_index("ix_test_questions_discipline", "test_questions", ["discipline"])
    op.create_index(
        "ix_test_questions_target_grade", "test_questions", ["target_grade"]
    )

    # ------------------------------------------------------------------
    # 5. test_sessions table
    # ------------------------------------------------------------------
    op.create_table(
        "test_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "participant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_grade", sa.String(20), nullable=False),
        sa.Column("discipline", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("irt_theta", sa.Float(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("questions_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("grade_assigned", sa.String(20), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'expired', 'abandoned')",
            name="ck_session_status",
        ),
        sa.CheckConstraint(
            "target_grade IN ('junior', 'middle', 'senior', 'lead')",
            name="ck_session_grade",
        ),
    )
    op.create_index(
        "ix_test_sessions_participant_id", "test_sessions", ["participant_id"]
    )
    # Partial unique index: only one in_progress session per participant
    op.execute(
        """
        CREATE UNIQUE INDEX uix_one_active_session
          ON test_sessions (participant_id)
         WHERE status = 'in_progress'
        """
    )

    # ------------------------------------------------------------------
    # 6. test_answers table
    # ------------------------------------------------------------------
    op.create_table(
        "test_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_questions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "session_id", "question_id", name="uq_answer_session_question"
        ),
    )
    op.create_index(
        "ix_test_answers_session_id", "test_answers", ["session_id"]
    )

    # ------------------------------------------------------------------
    # 7. Applications: add viewed_at column
    # ------------------------------------------------------------------
    op.add_column(
        "applications",
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "viewed_at")
    op.drop_table("test_answers")
    op.drop_index("uix_one_active_session", table_name="test_sessions")
    op.drop_table("test_sessions")
    op.drop_table("test_questions")
    op.drop_column("participants", "grade_locked_until")
    op.drop_column("employers", "industry")
    op.drop_column("employers", "description")
