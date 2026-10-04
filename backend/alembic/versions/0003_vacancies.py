"""vacancies and applications

Revision ID: 0003_vacancies
Revises: 0002_integrity
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_vacancies"
down_revision: Union[str, Sequence[str], None] = "0002_integrity"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("employer_id", UUID, sa.ForeignKey("employers.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("role", sa.String(50)),
        sa.Column("grade", sa.String(20)),
        sa.Column("discipline", sa.String(50)),
        sa.Column("min_rank", sa.String(10)),
        sa.Column("skills", JSONB, nullable=False, server_default="[]"),
        sa.Column("salary_from_gross", sa.Integer()),
        sa.Column("salary_to_gross", sa.Integer()),
        sa.Column("work_format", sa.String(20), nullable=False, server_default="remote"),
        sa.Column("allows_minors", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vacancies_employer_id", "vacancies", ["employer_id"])
    op.create_table(
        "applications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("vacancy_id", UUID, sa.ForeignKey("vacancies.id"), nullable=False),
        sa.Column("candidate_id", UUID, sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="applied"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("vacancy_id", "candidate_id", name="uq_application_pair"),
    )
    op.create_index("ix_applications_vacancy_id", "applications", ["vacancy_id"])
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])
    op.create_index(
        "uq_applications_open_pair",
        "applications",
        ["vacancy_id", "candidate_id"],
        unique=True,
        postgresql_where=sa.text("status = 'applied'"),
    )


def downgrade() -> None:
    op.drop_index("uq_applications_open_pair", table_name="applications")
    op.drop_index("ix_applications_candidate_id", table_name="applications")
    op.drop_index("ix_applications_vacancy_id", table_name="applications")
    op.drop_table("applications")
    op.drop_index("ix_vacancies_employer_id", table_name="vacancies")
    op.drop_table("vacancies")
