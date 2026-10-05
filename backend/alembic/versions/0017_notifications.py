"""Notifications: one row per hiring event for the side that has to act, mirrored by an e-mail.

Revision ID: 0017_notifications
Revises: 0016_erasure
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017_notifications"
down_revision = "0016_erasure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recipient_role", sa.String(20), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_recipient", "notifications", ["recipient_role", "recipient_id", "read_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_recipient", table_name="notifications")
    op.drop_table("notifications")
