"""HMAC of a served answer key, and a refresh-token generation.

Revision ID: 0026_answer_mac_refresh
Revises: 0025_credential_status
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0026_answer_mac_refresh"
down_revision = "0025_credential_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_session_items", sa.Column("answer_mac", sa.String(length=64), nullable=True))
    op.add_column(
        "participants",
        sa.Column("refresh_nonce", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "employers",
        sa.Column("refresh_nonce", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("employers", "refresh_nonce")
    op.drop_column("participants", "refresh_nonce")
    op.drop_column("test_session_items", "answer_mac")
