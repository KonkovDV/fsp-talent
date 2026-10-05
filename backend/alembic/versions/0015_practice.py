"""Short practice tasks formed from a vacancy, without touching the confirmed grade.

Revision ID: 0015_practice
Revises: 0014_vacancy_description
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_practice"
down_revision = "0014_vacancy_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "practice_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("topic", sa.String(40), nullable=False),
        sa.Column("family_id", sa.String(40), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer_index", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_practice_attempts_participant_id", "practice_attempts", ["participant_id"])
    op.add_column("participants", sa.Column("practice_topic", sa.String(40), nullable=True))
    op.add_column("participants", sa.Column("practice_ok", sa.Boolean(), nullable=True))
    op.add_column("participants", sa.Column("practice_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("participants", "practice_at")
    op.drop_column("participants", "practice_ok")
    op.drop_column("participants", "practice_topic")
    op.drop_index("ix_practice_attempts_participant_id", table_name="practice_attempts")
    op.drop_table("practice_attempts")
