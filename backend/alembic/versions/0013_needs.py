"""Employer needs: versioned search profiles with a shortlist.

A need is what the employer is looking for (role, grade, required and nice-to-have skills, industry, salary
range, job or internship). Every edit creates a new version, and a shortlisted candidate remembers the version
they were picked under, so a later change of requirements does not rewrite history.

Revision ID: 0013_needs
Revises: 0012_survey_cat
Create Date: 2026-10-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0013_needs"
down_revision = "0012_survey_cat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "needs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("employer_id", UUID(as_uuid=True), sa.ForeignKey("employers.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "need_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("need_id", UUID(as_uuid=True), sa.ForeignKey("needs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("params", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("need_id", "version", name="uq_need_version"),
    )
    op.create_table(
        "need_shortlist",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("need_id", UUID(as_uuid=True), sa.ForeignKey("needs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", UUID(as_uuid=True), sa.ForeignKey("participants.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="shortlisted"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("need_id", "participant_id", name="uq_need_shortlist"),
        sa.CheckConstraint("status IN ('shortlisted', 'invited', 'rejected')", name="ck_need_shortlist_status"),
    )


def downgrade() -> None:
    op.drop_table("need_shortlist")
    op.drop_table("need_versions")
    op.drop_table("needs")
