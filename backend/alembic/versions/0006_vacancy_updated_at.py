"""vacancies.updated_at

Revision ID: 0006_vacancy_updated_at
Revises: 0005_search_index
Create Date: 2026-10-04

The Vacancy ORM column was added in 53d8a3f. Without this column every
SELECT/INSERT on vacancies fails with UndefinedColumn.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_vacancy_updated_at"
down_revision: Union[str, Sequence[str], None] = "0005_search_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vacancies",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_column("vacancies", "updated_at")
