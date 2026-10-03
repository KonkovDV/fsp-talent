"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-03
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
TS = postgresql.TSVECTOR()


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "participants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("fsp_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("email", sa.String(200)),
        sa.Column("telegram", sa.String(64)),
        sa.Column("phone", sa.String(20)),
        sa.Column("birth_date", sa.Date()),
        sa.Column("region", sa.String(100)),
        sa.Column("experience_years", sa.Integer()),
        sa.Column("declared_grade", sa.String(20)),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("public_profile", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_minor", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("minor_consent_given", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("fsp_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_participants_fsp_id", "participants", ["fsp_id"])
    op.create_index("ix_participants_region", "participants", ["region"])

    op.create_table(
        "employers",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("inn", sa.String(12)),
        sa.Column("website", sa.String(200)),
        sa.Column("subscription_tier", sa.String(20), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "qualifications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("discipline", sa.String(50), nullable=False),
        sa.Column("rank", sa.String(10), nullable=False),
        sa.Column("issued_date", sa.Date()),
        sa.Column("certificate_number", sa.String(50)),
    )
    op.create_table(
        "results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("event_id", sa.String(100), nullable=False),
        sa.Column("event_name", sa.String(300), nullable=False),
        sa.Column("discipline", sa.String(50), nullable=False),
        sa.Column("competition_status", sa.String(30), nullable=False),
        sa.Column("place", sa.Integer(), nullable=False),
        sa.Column("total_participants", sa.Integer(), nullable=False),
        sa.Column("regions_count", sa.Integer()),
        sa.Column("is_team", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("team_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("role", sa.String(20), nullable=False, server_default="participant"),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("protocol_url", sa.String(500)),
        sa.Column("trust_level", sa.String(20), nullable=False, server_default="verified_fsp"),
        sa.Column("raw_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_results_participant_id", "results", ["participant_id"])

    op.create_table(
        "skills",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("raw_name", sa.String(200)),
        sa.Column("source_quote", sa.Text()),
        sa.Column("trust_level", sa.String(20), nullable=False, server_default="self_reported"),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("participant_id", "name", name="uq_participant_skill"),
    )
    op.create_index("ix_skills_participant_id", "skills", ["participant_id"])

    op.create_table(
        "discipline_scores",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("discipline", sa.String(50), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("sigma", sa.Float(), nullable=False),
        sa.Column("lcb", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("events_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("team_events_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_rank", sa.String(10)),
        sa.Column("top_event_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("scoring_version", sa.String(20), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("participant_id", "discipline", name="uq_participant_discipline"),
    )
    op.create_index("ix_discipline_scores_participant_id", "discipline_scores", ["participant_id"])

    op.create_table(
        "category_assignments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("primary_role", sa.String(50), nullable=False),
        sa.Column("grade", sa.String(20), nullable=False),
        sa.Column("grade_source", sa.String(20), nullable=False, server_default="default"),
        sa.Column("stack", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("explanation", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rules_version", sa.String(20), nullable=False, server_default="v2.0.0"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("participant_id"),
    )
    op.create_table(
        "profile_embeddings",
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_profile_embeddings_hnsw", "profile_embeddings", ["embedding"], postgresql_using="hnsw",
                    postgresql_ops={"embedding": "vector_cosine_ops"})
    op.create_table(
        "profile_search_index",
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("skills_text", sa.Text(), nullable=False),
        sa.Column("skills_tsv", TS, sa.Computed("to_tsvector('simple', skills_text)", persisted=True)),
        sa.Column("role", sa.String(50)),
        sa.Column("grade", sa.String(20)),
        sa.Column("region", sa.String(100)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_psi_skills_tsv", "profile_search_index", ["skills_tsv"], postgresql_using="gin")
    op.create_index("ix_psi_skills_trgm", "profile_search_index", ["skills_text"], postgresql_using="gin",
                    postgresql_ops={"skills_text": "gin_trgm_ops"})

    op.create_table(
        "offers",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("employer_id", UUID, sa.ForeignKey("employers.id"), nullable=False),
        sa.Column("candidate_id", UUID, sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("salary_from_gross", sa.Integer(), nullable=False),
        sa.Column("salary_to_gross", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("role", sa.String(100), nullable=False),
        sa.Column("work_format", sa.String(20), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("contacts_revealed_at", sa.DateTime(timezone=True)),
        sa.Column("employer_viewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "consent_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("actor_id", UUID, nullable=False),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_table(
        "access_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("employer_id", UUID, sa.ForeignKey("employers.id"), nullable=False),
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("access_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "verifiable_credentials",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("participant_id", UUID, sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("result_id", UUID, sa.ForeignKey("results.id")),
        sa.Column("credential_json", JSONB, nullable=False),
        sa.Column("proof_hex", sa.String(200), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_verifiable_credentials_participant_id", "verifiable_credentials", ["participant_id"])


def downgrade() -> None:
    for table in ("verifiable_credentials", "access_logs", "consent_logs", "offers", "profile_search_index",
                  "profile_embeddings", "category_assignments", "discipline_scores", "skills", "results",
                  "qualifications", "employers", "participants"):
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
