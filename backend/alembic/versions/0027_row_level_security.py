"""Row-level security on private rows.

Revision ID: 0027_row_level_security
Revises: 0026_answer_mac_refresh

The application role owns the tables, so the policies are forced. A request sets
app.participant_id or app.employer_id. app.bypass_rls = on is the seed, the worker
and the public pages. Item keys stay on test_session_items, which an employer cannot read.
"""
from __future__ import annotations

from alembic import op

revision = "0027_row_level_security"
down_revision = "0026_answer_mac_refresh"
branch_labels = None
depends_on = None

_ACTOR = "current_setting('app.bypass_rls', true) = 'on'"
_PARTICIPANT = "current_setting('app.participant_id', true)"
_EMPLOYER = "current_setting('app.employer_id', true)"


def _policy(table: str, using: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY {table}_actor ON {table} USING ({using})")


def upgrade() -> None:
    _policy("needs", f"{_ACTOR} OR employer_id::text = {_EMPLOYER}")
    _policy("need_versions", f"{_ACTOR} OR need_id IN (SELECT id FROM needs)")
    _policy("need_shortlist", f"{_ACTOR} OR need_id IN (SELECT id FROM needs)")
    _policy(
        "offers",
        f"{_ACTOR} OR employer_id::text = {_EMPLOYER} OR candidate_id::text = {_PARTICIPANT}",
    )
    _policy("offer_messages", f"{_ACTOR} OR offer_id IN (SELECT id FROM offers)")
    _policy(
        "test_sessions",
        f"{_ACTOR} OR participant_id::text = {_PARTICIPANT} OR {_EMPLOYER} <> ''",
    )
    _policy(
        "test_session_items",
        f"{_ACTOR} OR session_id IN (SELECT id FROM test_sessions "
        f"WHERE participant_id::text = {_PARTICIPANT})",
    )
    _policy(
        "grade_confirmations",
        f"{_ACTOR} OR participant_id::text = {_PARTICIPANT} OR {_EMPLOYER} <> ''",
    )


def downgrade() -> None:
    for table in (
        "grade_confirmations", "test_session_items", "test_sessions", "offer_messages",
        "offers", "need_shortlist", "need_versions", "needs",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_actor ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
