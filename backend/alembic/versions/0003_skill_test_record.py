"""Skill test record: share of correct answers in the latest finished session (F24b).

Revision ID: 0003_skill_test_record
Revises: 0002_survey_history

Three nullable columns on skills, so a card can tell "checked by a test, not confirmed" from
"never checked". A separate revision: a stand already at 0002 gets them by `alembic upgrade head`.
"""
from __future__ import annotations

from alembic import op

revision = "0003_skill_test_record"
down_revision = "0002_survey_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS test_share double precision")
    op.execute("ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS test_items integer")
    op.execute("ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS tested_at timestamp with time zone")


def downgrade() -> None:
    op.execute("ALTER TABLE public.skills DROP COLUMN IF EXISTS tested_at")
    op.execute("ALTER TABLE public.skills DROP COLUMN IF EXISTS test_items")
    op.execute("ALTER TABLE public.skills DROP COLUMN IF EXISTS test_share")
