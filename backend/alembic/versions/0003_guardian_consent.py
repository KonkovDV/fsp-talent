"""Consent of a legal representative for a candidate aged 15 to 17.

Revision ID: 0003_guardian_consent
Revises: 0002_offer_responded_at

The minor names the guardian's email; the guardian confirms by a signed link. Until then the card stays out
of search, comparison and invitations (minor_consent_given stays false).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_guardian_consent"
down_revision = "0002_offer_responded_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column("guardian_email", sa.String(200), nullable=True))
    op.add_column("participants", sa.Column("guardian_consent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("participants", "guardian_consent_at")
    op.drop_column("participants", "guardian_email")
