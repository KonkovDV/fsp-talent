"""Aggregate answer counts without exposing item keys.

Revision ID: 0028_answer_counts
Revises: 0027_row_level_security

Employers may read confirming sessions, and they must not read stems or keys.
Search needs only how many answers were right. The function turns the row-level
bypass on for that aggregate and puts the previous setting back before it returns.
"""
from __future__ import annotations

from alembic import op

revision = "0028_answer_counts"
down_revision = "0027_row_level_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_answer_counts(session_ids uuid[])
        RETURNS TABLE(session_id uuid, n bigint, correct bigint)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            prev text;
        BEGIN
            prev := current_setting('app.bypass_rls', true);
            PERFORM set_config('app.bypass_rls', 'on', true);
            BEGIN
                RETURN QUERY
                    SELECT i.session_id,
                           count(*)::bigint,
                           count(*) FILTER (WHERE i.is_correct IS TRUE)::bigint
                    FROM test_session_items AS i
                    WHERE i.session_id = ANY(session_ids)
                      AND i.answered_at IS NOT NULL
                      AND i.excluded IS FALSE
                    GROUP BY i.session_id;
            EXCEPTION
                WHEN OTHERS THEN
                    PERFORM set_config('app.bypass_rls', coalesce(prev, ''), true);
                    RAISE;
            END;
            PERFORM set_config('app.bypass_rls', coalesce(prev, ''), true);
        END;
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app_answer_counts(uuid[]) FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_answer_counts(uuid[])")
