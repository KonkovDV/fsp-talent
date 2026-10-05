"""Vacancy description, so a test can be formed from the text and not only from skill tags.

Revision ID: 0014_vacancy_description
Revises: 0013_needs
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_vacancy_description"
down_revision = "0013_needs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("vacancies", "description")
