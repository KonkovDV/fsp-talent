"""Whether the candidate is looking for work.

Revision ID: 0004_job_search
Revises: 0003_guardian_consent

active: looking now. open: will consider an offer (the default). not_looking: the card leaves search
and shortlists. The publication consent stays as it was.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_job_search"
down_revision = "0003_guardian_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column(
        "job_search", sa.String(20), nullable=False, server_default="open"))
    op.create_check_constraint(
        "ck_participants_job_search", "participants",
        "job_search IN ('active', 'open', 'not_looking')")


def downgrade() -> None:
    op.drop_constraint("ck_participants_job_search", "participants", type_="check")
    op.drop_column("participants", "job_search")
