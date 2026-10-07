"""Revocation time for a stored verifiable credential.

Revision ID: 0025_credential_status
Revises: 0024_offer_feedback
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_credential_status"
down_revision = "0024_offer_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("verifiable_credentials", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("verifiable_credentials", "revoked_at")
