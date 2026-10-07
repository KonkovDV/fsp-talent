"""Interview slots after an accepted invitation.

Revision ID: 0006_interviews
Revises: 0005_complaints

The employer offers one to three times. The candidate picks one. The outcome stays
on the chosen row and later changes P(accept) for the next invitation of this company.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_interviews"
down_revision = "0005_complaints"
branch_labels = None
depends_on = None

_ACTOR = (
    "current_setting('app.bypass_rls', true) = 'on' "
    "OR offer_id IN (SELECT id FROM offers WHERE "
    "employer_id::text = current_setting('app.employer_id', true) "
    "OR candidate_id::text = current_setting('app.participant_id', true))"
)


def upgrade() -> None:
    op.create_table(
        "interview_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("place", sa.Text(), nullable=True),
        sa.Column("chosen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("outcome", sa.String(20), nullable=True),
        sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("format IN ('online', 'office', 'phone')", name="ck_interview_format"),
        sa.CheckConstraint(
            "outcome IS NULL OR (chosen AND outcome IN ('passed', 'failed', 'no_show'))",
            name="ck_interview_outcome",
        ),
    )
    op.create_index("ix_interview_slots_offer_id", "interview_slots", ["offer_id"])
    op.create_index(
        "uq_interview_slots_chosen", "interview_slots", ["offer_id"],
        unique=True, postgresql_where=sa.text("chosen"),
    )
    op.execute("ALTER TABLE interview_slots ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY interview_slots_actor ON interview_slots "
        f"USING ({_ACTOR}) WITH CHECK ({_ACTOR})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS interview_slots_actor ON interview_slots")
    op.drop_index("uq_interview_slots_chosen", table_name="interview_slots")
    op.drop_index("ix_interview_slots_offer_id", table_name="interview_slots")
    op.drop_table("interview_slots")
