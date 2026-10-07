"""Drop superuser rights on application connections.

Revision ID: 0029_app_role
Revises: 0028_answer_counts

A superuser ignores row-level security even when the policies are forced.
The API, worker and seed use the application engine, which becomes fsp_app
after connecting. Migrations keep the owner connection and can still change
the schema.
"""
from __future__ import annotations

from alembic import op

revision = "0029_app_role"
down_revision = "0028_answer_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CREATE ROLE is rejected inside Alembic's transaction.
    with op.get_context().autocommit_block():
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fsp_app') THEN
                    CREATE ROLE fsp_app NOLOGIN NOSUPERUSER NOBYPASSRLS;
                END IF;
            END $$;
            """
        )
    op.execute("GRANT USAGE ON SCHEMA public TO fsp_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fsp_app"
    )
    op.execute("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO fsp_app")
    op.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO fsp_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fsp_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO fsp_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO fsp_app"
    )


def downgrade() -> None:
    op.execute("REVOKE ALL ON SCHEMA public FROM fsp_app")
    op.execute("DROP OWNED BY fsp_app")
    with op.get_context().autocommit_block():
        op.execute("DROP ROLE IF EXISTS fsp_app")
