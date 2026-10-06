"""Skill passport: the date a skill became evidence, not just a declaration.

Revision ID: 0019_skill_confirmed_at
Revises: 0018_typed_answers
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_skill_confirmed_at"
down_revision = "0018_typed_answers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE skills SET confirmed_at = created_at "
        "WHERE trust_level IN ('test_confirmed', 'resume_confirmed')"
    )


def downgrade() -> None:
    op.drop_column("skills", "confirmed_at")
