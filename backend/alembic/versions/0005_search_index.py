"""search indexes: is_visible, psi role/grade

Revision ID: 0005_search_index
Revises: 0004_tech_debt
Create Date: 2026-10-04

Three BTree indexes that help the employer candidate search avoid full
sequential scans:

  ix_participants_is_visible
    Every employer search begins with WHERE is_visible = TRUE.
    Without an index this is a full sequential scan of the participants table.

  ix_psi_role / ix_psi_grade
    profile_search_index role= and grade= query-param filters.
    GIN indexes on skills_tsv / skills_text (from 0001) already cover the
    text-search path; these BTree indexes handle the structured-filter path.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_search_index"
down_revision: Union[str, Sequence[str], None] = "0004_tech_debt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_participants_is_visible", "participants", ["is_visible"])
    op.create_index("ix_psi_role",  "profile_search_index", ["role"])
    op.create_index("ix_psi_grade", "profile_search_index", ["grade"])


def downgrade() -> None:
    op.drop_index("ix_psi_grade", table_name="profile_search_index")
    op.drop_index("ix_psi_role",  table_name="profile_search_index")
    op.drop_index("ix_participants_is_visible", table_name="participants")
