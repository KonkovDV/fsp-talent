"""Drop the legacy fixed question bank: the adaptive test generates every item from a parametric family.

test_questions held 22 hand-written questions that no code path served since the adaptive test (0012).
A stored bank is exactly what the case warns against: answers spread between candidates.

Revision ID: 0021_drop_legacy_bank
Revises: 0020_intern_grade
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021_drop_legacy_bank"
down_revision = "0020_intern_grade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("test_answers")
    op.drop_table("test_questions")


def downgrade() -> None:
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("question_type IN ('mcq', 'open')", name="ck_question_type"),
        sa.CheckConstraint("target_grade IN ('intern', 'junior', 'middle', 'senior', 'lead')",
                           name="ck_question_grade"),
    )
    op.create_index("ix_test_questions_discipline", "test_questions", ["discipline"])
    op.create_index("ix_test_questions_target_grade", "test_questions", ["target_grade"])
    op.create_table(
        "test_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("test_questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id", "question_id", name="uq_answer_session_question"),
    )
    op.create_index("ix_test_answers_session_id", "test_answers", ["session_id"])
