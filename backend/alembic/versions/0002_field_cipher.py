"""Encrypt contact fields with AES-256-GCM.

Revision ID: 0002_field_cipher
Revises: 0001_initial

Existing plaintext is sealed in this step. Login uses email_bindex, an HMAC,
not the ciphertext. Downgrade opens the values back.
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa

from alembic import op
from app.services.field_cipher import PREFIX, blind_index, open_seal, seal

revision = "0002_field_cipher"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _seal_row(owner: str, table: str, column: str, value):
    if value is None or value == "" or (isinstance(value, str) and value.startswith(PREFIX)):
        return value
    return seal(owner, table, column, value)


def _open_row(owner: str, table: str, column: str, value):
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value
    return open_seal(owner, table, column, value)


def upgrade() -> None:
    op.execute("ALTER TABLE participants ALTER COLUMN email TYPE text")
    op.execute("ALTER TABLE participants ALTER COLUMN phone TYPE text")
    op.execute("ALTER TABLE participants ALTER COLUMN telegram TYPE text")
    op.execute("ALTER TABLE participants ALTER COLUMN guardian_email TYPE text")
    op.execute("ALTER TABLE participants ADD COLUMN email_bindex varchar(64)")
    op.execute("ALTER TABLE participants DROP CONSTRAINT IF EXISTS participants_email_key")
    op.execute("CREATE UNIQUE INDEX uq_participants_email_bindex ON participants (email_bindex)")
    op.execute("ALTER TABLE employers ALTER COLUMN email TYPE text")
    op.execute("ALTER TABLE employers ADD COLUMN email_bindex varchar(64)")
    op.execute("ALTER TABLE employers DROP CONSTRAINT IF EXISTS employers_email_key")
    op.execute("CREATE UNIQUE INDEX uq_employers_email_bindex ON employers (email_bindex)")
    op.execute("ALTER TABLE offers ALTER COLUMN contact_method TYPE text")
    op.execute("ALTER TABLE email_verifications ALTER COLUMN email TYPE text")
    op.execute("ALTER TABLE email_verifications ADD COLUMN email_bindex varchar(64)")
    op.execute("CREATE INDEX ix_email_verifications_bindex ON email_verifications (email_bindex)")
    bind = op.get_bind()
    people = bind.execute(sa.text(
        "SELECT id::text, email, phone, telegram, guardian_email FROM participants")).all()
    for owner, email, phone, telegram, guardian in people:
        bind.execute(sa.text(
            """
            UPDATE participants
               SET email = :email, phone = :phone, telegram = :telegram,
                   guardian_email = :guardian, email_bindex = :bindex
             WHERE id = :id
            """), {
            "id": uuid.UUID(owner),
            "email": _seal_row(owner, "participants", "email", email),
            "phone": _seal_row(owner, "participants", "phone", phone),
            "telegram": _seal_row(owner, "participants", "telegram", telegram),
            "guardian": _seal_row(owner, "participants", "guardian_email", guardian),
            "bindex": blind_index(email) if email else None,
        })
    companies = bind.execute(sa.text("SELECT id::text, email FROM employers")).all()
    for owner, email in companies:
        bind.execute(sa.text(
            "UPDATE employers SET email = :email, email_bindex = :bindex WHERE id = :id"), {
            "id": uuid.UUID(owner),
            "email": _seal_row(owner, "employers", "email", email),
            "bindex": blind_index(email) if email else None,
        })
    offers = bind.execute(sa.text(
        "SELECT id::text, contact_method FROM offers WHERE contact_method IS NOT NULL")).all()
    for owner, contact in offers:
        bind.execute(sa.text(
            "UPDATE offers SET contact_method = :contact WHERE id = :id"), {
            "id": uuid.UUID(owner),
            "contact": _seal_row(owner, "offers", "contact_method", contact),
        })
    letters = bind.execute(sa.text("SELECT id::text, email FROM email_verifications")).all()
    for owner, email in letters:
        bind.execute(sa.text(
            "UPDATE email_verifications SET email = :email, email_bindex = :bindex WHERE id = :id"), {
            "id": uuid.UUID(owner),
            "email": _seal_row(owner, "email_verifications", "email", email),
            "bindex": blind_index(email) if email else None,
        })


def downgrade() -> None:
    bind = op.get_bind()
    people = bind.execute(sa.text(
        "SELECT id::text, email, phone, telegram, guardian_email FROM participants")).all()
    for owner, email, phone, telegram, guardian in people:
        bind.execute(sa.text(
            """
            UPDATE participants
               SET email = :email, phone = :phone, telegram = :telegram, guardian_email = :guardian
             WHERE id = :id
            """), {
            "id": uuid.UUID(owner),
            "email": _open_row(owner, "participants", "email", email),
            "phone": _open_row(owner, "participants", "phone", phone),
            "telegram": _open_row(owner, "participants", "telegram", telegram),
            "guardian": _open_row(owner, "participants", "guardian_email", guardian),
        })
    companies = bind.execute(sa.text("SELECT id::text, email FROM employers")).all()
    for owner, email in companies:
        bind.execute(sa.text("UPDATE employers SET email = :email WHERE id = :id"), {
            "id": uuid.UUID(owner), "email": _open_row(owner, "employers", "email", email)})
    offers = bind.execute(sa.text(
        "SELECT id::text, contact_method FROM offers WHERE contact_method IS NOT NULL")).all()
    for owner, contact in offers:
        bind.execute(sa.text("UPDATE offers SET contact_method = :contact WHERE id = :id"), {
            "id": uuid.UUID(owner), "contact": _open_row(owner, "offers", "contact_method", contact)})
    letters = bind.execute(sa.text("SELECT id::text, email FROM email_verifications")).all()
    for owner, email in letters:
        bind.execute(sa.text("UPDATE email_verifications SET email = :email WHERE id = :id"), {
            "id": uuid.UUID(owner), "email": _open_row(owner, "email_verifications", "email", email)})
    op.execute("DROP INDEX IF EXISTS uq_participants_email_bindex")
    op.execute("ALTER TABLE participants DROP COLUMN IF EXISTS email_bindex")
    op.execute("ALTER TABLE participants ALTER COLUMN email TYPE varchar(200)")
    op.execute("ALTER TABLE participants ALTER COLUMN phone TYPE varchar(20)")
    op.execute("ALTER TABLE participants ALTER COLUMN telegram TYPE varchar(64)")
    op.execute("ALTER TABLE participants ALTER COLUMN guardian_email TYPE varchar(200)")
    op.execute("ALTER TABLE participants ADD CONSTRAINT participants_email_key UNIQUE (email)")
    op.execute("DROP INDEX IF EXISTS uq_employers_email_bindex")
    op.execute("ALTER TABLE employers DROP COLUMN IF EXISTS email_bindex")
    op.execute("ALTER TABLE employers ALTER COLUMN email TYPE varchar(200)")
    op.execute("ALTER TABLE employers ADD CONSTRAINT employers_email_key UNIQUE (email)")
    op.execute("ALTER TABLE offers ALTER COLUMN contact_method TYPE varchar(300)")
    op.execute("DROP INDEX IF EXISTS ix_email_verifications_bindex")
    op.execute("ALTER TABLE email_verifications DROP COLUMN IF EXISTS email_bindex")
    op.execute("ALTER TABLE email_verifications ALTER COLUMN email TYPE varchar(200)")
