"""A finished test can be sent for a manual look. The grade stays.

Revision ID: 0003_grade_disputes
Revises: 0002_work_formats

The row is the candidate's. An employer policy does not match it, so the
moderation desk does not see the appeal. One session can be disputed once.
"""
from __future__ import annotations

from alembic import op

revision = "0003_grade_disputes"
down_revision = "0002_work_formats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE grade_disputes (
            id uuid PRIMARY KEY,
            participant_id uuid NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
            session_id uuid NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_grade_dispute_session UNIQUE (session_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_grade_disputes_participant ON grade_disputes (participant_id)")
    op.execute("ALTER TABLE grade_disputes ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY grade_disputes_actor ON grade_disputes
        USING (
            current_setting('app.bypass_rls', true) = 'on'
            OR participant_id::text = current_setting('app.participant_id', true)
        )
        WITH CHECK (
            current_setting('app.bypass_rls', true) = 'on'
            OR participant_id::text = current_setting('app.participant_id', true)
        )
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON grade_disputes TO fsp_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE grade_disputes")
