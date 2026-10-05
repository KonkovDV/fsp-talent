"""Email identity for both roles, candidates without FSP history, versioned consents.

TZ 2.2 п.4: registration by email with confirmation. TZ 2.1: a candidate may have no FSP history,
so participants.fsp_id becomes optional (PostgreSQL UNIQUE allows many NULLs).
152-FZ art. 9 (156-FZ, from 01.09.2025): consent is a separate document; we keep the exact version
and SHA-256 of the text the person agreed to.

Revision ID: 0011_identity_consents
Revises: 0010_offer_contact_viewed
Create Date: 2026-10-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0011_identity_consents"
down_revision = "0010_offer_contact_viewed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("participants", "fsp_id", existing_type=sa.String(64), nullable=True)
    op.add_column("participants", sa.Column("password_hash", sa.String(200), nullable=True))
    op.add_column("participants", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("participants", sa.Column("fsp_linked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("employers", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    # Accounts created before this migration were usable without confirmation; keep them usable.
    op.execute("UPDATE employers SET email_verified_at = now() WHERE email_verified_at IS NULL")
    op.execute("UPDATE participants SET fsp_linked_at = created_at WHERE fsp_id IS NOT NULL")
    op.execute("UPDATE participants SET email = lower(email) WHERE email IS NOT NULL")
    op.execute("UPDATE employers SET email = lower(email)")

    op.create_table(
        "email_verifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("subject_type IN ('participant', 'employer')", name="ck_email_verification_subject"),
        sa.CheckConstraint("purpose IN ('verify', 'reset')", name="ck_email_verification_purpose"),
    )
    op.create_index("ix_email_verifications_email", "email_verifications", ["email"])
    op.create_index("ix_email_verifications_subject", "email_verifications", ["subject_type", "subject_id"])

    op.create_table(
        "consents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("given_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.CheckConstraint("subject_type IN ('participant', 'employer')", name="ck_consent_subject"),
    )
    op.create_index("ix_consents_subject", "consents", ["subject_type", "subject_id", "kind"])
    # One active consent per document kind; withdrawn rows stay as history.
    op.create_index(
        "uq_consents_active", "consents", ["subject_type", "subject_id", "kind"], unique=True,
        postgresql_where=sa.text("withdrawn_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_consents_active", table_name="consents")
    op.drop_index("ix_consents_subject", table_name="consents")
    op.drop_table("consents")
    op.drop_index("ix_email_verifications_subject", table_name="email_verifications")
    op.drop_index("ix_email_verifications_email", table_name="email_verifications")
    op.drop_table("email_verifications")
    op.drop_column("employers", "email_verified_at")
    op.drop_column("participants", "fsp_linked_at")
    op.drop_column("participants", "email_verified_at")
    op.drop_column("participants", "password_hash")
    # Candidates who registered without FSP cannot satisfy NOT NULL. They keep their rows (offers and
    # consent logs point at them) under a placeholder id that no FSP account can have.
    op.execute("UPDATE participants SET fsp_id = 'NOFSP-' || id::text WHERE fsp_id IS NULL")
    op.alter_column("participants", "fsp_id", existing_type=sa.String(64), nullable=False)
