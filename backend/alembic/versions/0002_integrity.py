"""integrity: one pending offer per employer/candidate, sane result ranges

Revision ID: 0002_integrity
Revises: 0001_initial
Create Date: 2026-10-04

CHECK constraints are added NOT VALID: they are enforced for every new or updated row,
but existing demo rows are not re-scanned, so the upgrade cannot fail on legacy data.
Run `ALTER TABLE ... VALIDATE CONSTRAINT ...` once the data is known to be clean.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002_integrity"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels = None
depends_on = None

RESULT_CHECKS = {
    "ck_results_place_positive": "place >= 1",
    "ck_results_total_positive": "total_participants >= 1",
    "ck_results_place_in_field": "place <= total_participants",
    "ck_results_team_size_positive": "team_size >= 1",
}
OFFER_CHECKS = {
    "ck_offers_salary_range": "salary_to_gross >= salary_from_gross",
}


def upgrade() -> None:
    # Keep only the newest pending offer per pair before the unique index is built.
    op.execute("""
        UPDATE offers o SET status = 'expired'
        WHERE o.status = 'pending' AND EXISTS (
            SELECT 1 FROM offers n
            WHERE n.employer_id = o.employer_id AND n.candidate_id = o.candidate_id
              AND n.status = 'pending'
              AND (n.created_at > o.created_at OR (n.created_at = o.created_at AND n.id > o.id)))
    """)
    op.create_index("uq_offers_pending_pair", "offers", ["employer_id", "candidate_id"], unique=True,
                    postgresql_where=sa.text("status = 'pending'"))
    op.create_index("ix_offers_candidate_id", "offers", ["candidate_id"])
    op.create_index("ix_offers_employer_id", "offers", ["employer_id"])
    for name, expr in RESULT_CHECKS.items():
        op.execute(f"ALTER TABLE results ADD CONSTRAINT {name} CHECK ({expr}) NOT VALID")
    for name, expr in OFFER_CHECKS.items():
        op.execute(f"ALTER TABLE offers ADD CONSTRAINT {name} CHECK ({expr}) NOT VALID")


def downgrade() -> None:
    for name in OFFER_CHECKS:
        op.execute(f"ALTER TABLE offers DROP CONSTRAINT IF EXISTS {name}")
    for name in RESULT_CHECKS:
        op.execute(f"ALTER TABLE results DROP CONSTRAINT IF EXISTS {name}")
    op.drop_index("ix_offers_employer_id", table_name="offers")
    op.drop_index("ix_offers_candidate_id", table_name="offers")
    op.drop_index("uq_offers_pending_pair", table_name="offers")
