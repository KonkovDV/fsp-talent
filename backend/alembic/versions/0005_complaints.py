"""Complaints about an invitation or a vacancy, and a hold on new invitations.

Revision ID: 0005_complaints
Revises: 0004_job_search

A candidate files one complaint per object. When enough different people complain
and the Wilson lower bound of that share is high, new invitations wait for a manual release.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_complaints"
down_revision = "0004_job_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "complaints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offers.id"), nullable=True),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vacancies.id"), nullable=True),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(offer_id IS NOT NULL AND vacancy_id IS NULL) OR (offer_id IS NULL AND vacancy_id IS NOT NULL)",
            name="ck_complaints_one_object",
        ),
        sa.CheckConstraint(
            "reason IN ('не_вакансия', 'сбор_данных', 'зарплата_не_та', 'оскорбление', 'другое')",
            name="ck_complaints_reason",
        ),
        sa.UniqueConstraint("participant_id", "offer_id", name="uq_complaints_participant_offer"),
        sa.UniqueConstraint("participant_id", "vacancy_id", name="uq_complaints_participant_vacancy"),
    )
    op.create_index("ix_complaints_participant_id", "complaints", ["participant_id"])
    op.execute("ALTER TABLE complaints ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY complaints_actor ON complaints USING ("
        "current_setting('app.bypass_rls', true) = 'on' "
        "OR participant_id::text = current_setting('app.participant_id', true)"
        ") WITH CHECK ("
        "current_setting('app.bypass_rls', true) = 'on' "
        "OR participant_id::text = current_setting('app.participant_id', true)"
        ")"
    )
    op.add_column("employers", sa.Column("invites_paused_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("employers", "invites_paused_at")
    op.execute("DROP POLICY IF EXISTS complaints_actor ON complaints")
    op.drop_index("ix_complaints_participant_id", table_name="complaints")
    op.drop_table("complaints")
