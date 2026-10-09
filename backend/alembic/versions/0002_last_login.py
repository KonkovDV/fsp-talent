"""When a participant last signed in with a password.

Revision ID: 0002_last_login
Revises: 0001_initial

Nullable. Existing rows stay empty, which the jury button reads as "never used".
"""
from __future__ import annotations

from alembic import op

revision = "0002_last_login"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.participants "
        "ADD COLUMN IF NOT EXISTS last_login_at timestamp with time zone"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.participants DROP COLUMN IF EXISTS last_login_at")
