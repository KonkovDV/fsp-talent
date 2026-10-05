"""participants.assessed_grade / assessed_at: grade confirmed by a completed test.

Revision ID: 0009_assessed_grade
Revises: 0008
Create Date: 2026-10-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_assessed_grade"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column("assessed_grade", sa.String(20), nullable=True))
    op.add_column("participants", sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_participants_assessed_grade", "participants",
        "assessed_grade IS NULL OR assessed_grade IN ('junior', 'middle', 'senior', 'lead')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_participants_assessed_grade", "participants", type_="check")
    op.drop_column("participants", "assessed_at")
    op.drop_column("participants", "assessed_grade")
