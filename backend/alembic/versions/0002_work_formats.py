"""Candidate work formats for the search filter.

Revision ID: 0002_work_formats
Revises: 0001_initial

The column is not an input of the match score. An empty list means the person
did not choose a format, and the filter leaves them in the list.
"""
from __future__ import annotations

from alembic import op

revision = "0002_work_formats"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE participants ADD COLUMN work_formats jsonb NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE participants DROP COLUMN work_formats")
