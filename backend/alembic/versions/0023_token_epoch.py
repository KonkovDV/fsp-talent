"""Password change invalidates outstanding access and refresh tokens.

Revision ID: 0023_token_epoch
Revises: 0022_employer_tasks
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_token_epoch"
down_revision = "0022_employer_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column("token_epoch", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("employers", sa.Column("token_epoch", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("employers", "token_epoch")
    op.drop_column("participants", "token_epoch")
