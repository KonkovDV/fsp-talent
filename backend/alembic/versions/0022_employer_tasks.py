"""Employer tasks, per-company contact revocation and messages after an accepted invitation.

- employer_tasks / task_submissions: tasks an employer writes (TZ 2.1, regular tasks). A number or a choice
  is checked by the system against the reference; an open answer is reviewed by the employer.
- participants.employer_task_*: the latest verdict, shown on the anonymous card as a fresh signal.
- offers.contacts_revoked_at: the candidate closed the contacts for one company after accepting.
- offer_messages: a short thread per accepted invitation.

Revision ID: 0022_employer_tasks
Revises: 0021_drop_legacy_bank
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_employer_tasks"
down_revision = "0021_drop_legacy_bank"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employer_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("employers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("vacancies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("answer_type", sa.String(10), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("correct_index", sa.Integer(), nullable=True),
        sa.Column("reference_number", sa.String(40), nullable=True),
        sa.Column("visibility", sa.String(10), nullable=False),
        sa.Column("specialization", sa.String(30), nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("answer_type IN ('number', 'choice', 'open')", name="ck_employer_tasks_answer_type"),
        sa.CheckConstraint(
            "(visibility = 'public' AND specialization IS NOT NULL AND candidate_id IS NULL) OR "
            "(visibility = 'addressed' AND candidate_id IS NOT NULL)", name="ck_employer_tasks_audience"),
    )
    op.create_index("ix_employer_tasks_employer_id", "employer_tasks", ["employer_id"])
    op.create_index("ix_employer_tasks_public", "employer_tasks", ["visibility", "specialization", "is_open"])
    op.create_index("ix_employer_tasks_candidate", "employer_tasks", ["candidate_id"])
    op.create_table(
        "task_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("employer_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answer_index", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("task_id", "participant_id", name="uq_task_submission"),
    )
    op.create_index("ix_task_submissions_task_id", "task_submissions", ["task_id"])
    op.create_index("ix_task_submissions_participant_id", "task_submissions", ["participant_id"])
    op.add_column("participants", sa.Column("employer_task_title", sa.String(200), nullable=True))
    op.add_column("participants", sa.Column("employer_task_passed", sa.Boolean(), nullable=True))
    op.add_column("participants", sa.Column("employer_task_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("offers", sa.Column("contacts_revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "offer_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_role", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_offer_messages_offer_id", "offer_messages", ["offer_id"])


def downgrade() -> None:
    op.drop_index("ix_offer_messages_offer_id", table_name="offer_messages")
    op.drop_table("offer_messages")
    op.drop_column("offers", "contacts_revoked_at")
    op.drop_column("participants", "employer_task_at")
    op.drop_column("participants", "employer_task_passed")
    op.drop_column("participants", "employer_task_title")
    op.drop_index("ix_task_submissions_participant_id", table_name="task_submissions")
    op.drop_index("ix_task_submissions_task_id", table_name="task_submissions")
    op.drop_table("task_submissions")
    op.drop_index("ix_employer_tasks_candidate", table_name="employer_tasks")
    op.drop_index("ix_employer_tasks_public", table_name="employer_tasks")
    op.drop_index("ix_employer_tasks_employer_id", table_name="employer_tasks")
    op.drop_table("employer_tasks")
