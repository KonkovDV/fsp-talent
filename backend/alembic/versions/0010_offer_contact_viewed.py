"""offers.contact_method and offers.candidate_viewed_at (TZ 2.2 п.2, п.3).

Revision ID: 0010_offer_contact_viewed
Revises: 0009_assessed_grade
Create Date: 2026-10-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_offer_contact_viewed"
down_revision = "0009_assessed_grade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("contact_method", sa.String(300), nullable=True))
    op.add_column("offers", sa.Column("candidate_viewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("offers", "candidate_viewed_at")
    op.drop_column("offers", "contact_method")
