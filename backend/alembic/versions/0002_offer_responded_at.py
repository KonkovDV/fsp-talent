"""When the candidate answered an invitation.

Revision ID: 0002_offer_responded_at
Revises: 0001_initial

A declined invitation starts a 30-day pause before the same company may invite the same person again;
the pause is counted from this moment. Old rows keep NULL and fall back to the creation time.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_offer_responded_at"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_offers_pair_rejected", "offers", ["employer_id", "candidate_id"],
                    postgresql_where=sa.text("status = 'rejected'"))


def downgrade() -> None:
    op.drop_index("ix_offers_pair_rejected", table_name="offers")
    op.drop_column("offers", "responded_at")
