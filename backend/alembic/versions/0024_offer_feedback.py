"""Decline reason, salary expectation, profile version, leak CUSUM.

Revision ID: 0024_offer_feedback
Revises: 0023_token_epoch
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_offer_feedback"
down_revision = "0023_token_epoch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column("profile_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("participants", sa.Column("salary_from_gross", sa.Integer(), nullable=True))
    op.add_column("participants", sa.Column("salary_to_gross", sa.Integer(), nullable=True))
    op.add_column("offers", sa.Column("decline_reason", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_offer_decline_reason", "offers",
        "decline_reason IS NULL OR decline_reason IN ('salary', 'format', 'stack', 'not_looking', 'other')",
    )
    op.add_column("item_stats", sa.Column("cusum", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("item_stats", "cusum")
    op.drop_constraint("ck_offer_decline_reason", "offers", type_="check")
    op.drop_column("offers", "decline_reason")
    op.drop_column("participants", "salary_to_gross")
    op.drop_column("participants", "salary_from_gross")
    op.drop_column("participants", "profile_version")
