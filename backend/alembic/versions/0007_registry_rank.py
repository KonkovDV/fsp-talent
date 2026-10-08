"""Rank as a registry fact next to the discipline score.

Revision ID: 0007_registry_rank
Revises: 0006_interviews

best_rank stays, but values written by the old place ladder are cleared: they were not orders.
Downgrade drops the two new columns and does not restore those values.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_registry_rank"
down_revision = "0006_interviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discipline_scores", sa.Column("rank_assigned_at", sa.Date(), nullable=True))
    op.add_column("discipline_scores", sa.Column("rank_order_ref", sa.String(length=64), nullable=True))
    op.execute("UPDATE discipline_scores SET best_rank = NULL")


def downgrade() -> None:
    op.drop_column("discipline_scores", "rank_order_ref")
    op.drop_column("discipline_scores", "rank_assigned_at")
