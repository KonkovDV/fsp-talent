"""Candidate erasure: deleted_at marks an account whose personal data was removed (152-FZ, art. 21).

Revision ID: 0016_erasure
Revises: 0015_practice
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_erasure"
down_revision = "0015_practice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("participants", "deleted_at")
