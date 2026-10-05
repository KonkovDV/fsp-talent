"""Typed answers: a code item with a whole-number answer is answered by typing it, without options.

Revision ID: 0018_typed_answers
Revises: 0017_notifications
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_typed_answers"
down_revision = "0017_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_session_items",
                  sa.Column("typed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("test_session_items", sa.Column("answer_text", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("test_session_items", "answer_text")
    op.drop_column("test_session_items", "typed")
