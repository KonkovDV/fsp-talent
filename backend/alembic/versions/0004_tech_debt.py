"""tech-debt: audit indexes + rename proof_hex to proof_value

Revision ID: 0004_tech_debt
Revises: 0003_vacancies
Create Date: 2026-10-04

Changes
-------
- ix_consent_logs_participant_id  -- 152-FZ audit queries are always by participant
- ix_access_logs_participant_id   -- same pattern for employer access log
- verifiable_credentials.proof_hex -> proof_value
  Naming now matches the W3C VC Data Model 2.0 "proofValue" field.
  The value itself (base58-multibase Ed25519 signature) is unchanged.

NOTE: uq_offers_pending_pair (partial unique index on offers) was already
created in 0002_integrity; nothing to do here for that item.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_tech_debt"
down_revision: Union[str, Sequence[str], None] = "0003_vacancies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_consent_logs_participant_id", "consent_logs", ["participant_id"])
    op.create_index("ix_access_logs_participant_id",  "access_logs",  ["participant_id"])
    op.alter_column("verifiable_credentials", "proof_hex", new_column_name="proof_value")


def downgrade() -> None:
    op.alter_column("verifiable_credentials", "proof_value", new_column_name="proof_hex")
    op.drop_index("ix_access_logs_participant_id",  table_name="access_logs")
    op.drop_index("ix_consent_logs_participant_id", table_name="consent_logs")
