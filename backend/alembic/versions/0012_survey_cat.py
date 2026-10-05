"""Survey (specialization, industry, goal), confirmed grades per specialization, adaptive test v2.

TZ 2.1: the category comes from the survey (industry, specialization), the declared grade and a test.
A grade confirmed for one specialization says nothing about another, so confirmations are stored per
specialization. Test v2 serves items one at a time from parametric families and keeps per-item statistics
for calibration and leak monitoring.

Revision ID: 0012_survey_cat
Revises: 0011_identity_consents
Create Date: 2026-10-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0012_survey_cat"
down_revision = "0011_identity_consents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column("specialization", sa.String(30), nullable=True))
    op.add_column("participants", sa.Column("industry", sa.String(40), nullable=True))
    op.add_column("participants", sa.Column("work_goal", sa.String(20), nullable=True))
    op.add_column("participants", sa.Column("survey_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_participants_specialization", "participants", ["specialization"])

    op.create_table(
        "grade_confirmations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("participant_id", UUID(as_uuid=True),
                  sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("specialization", sa.String(30), nullable=False),
        sa.Column("grade", sa.String(20), nullable=False),
        sa.Column("p_pass", sa.Float, nullable=True),
        sa.Column("theta", sa.Float, nullable=True),
        sa.Column("se", sa.Float, nullable=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("participant_id", "specialization", name="uq_grade_confirmation_spec"),
        sa.CheckConstraint("grade IN ('junior', 'middle', 'senior', 'lead')", name="ck_grade_confirmation_grade"),
    )
    # Earlier confirmations had no specialization; attach them to the role the profile had.
    op.execute("""
        INSERT INTO grade_confirmations (id, participant_id, specialization, grade, confirmed_at, locked_until)
        SELECT gen_random_uuid(), p.id, COALESCE(c.primary_role, 'fullstack'), p.assessed_grade,
               COALESCE(p.assessed_at, now()), p.grade_locked_until
        FROM participants p LEFT JOIN category_assignments c ON c.participant_id = p.id
        WHERE p.assessed_grade IS NOT NULL
    """)

    op.add_column("test_sessions", sa.Column("specialization", sa.String(30), nullable=True))
    op.add_column("test_sessions", sa.Column("engine", sa.String(20), nullable=False, server_default="fixed_v1"))
    op.add_column("test_sessions", sa.Column("p_pass", sa.Float, nullable=True))
    op.add_column("test_sessions", sa.Column("p_upgrade", sa.Float, nullable=True))
    op.add_column("test_sessions", sa.Column("theta_se", sa.Float, nullable=True))
    op.add_column("test_sessions", sa.Column("items_count", sa.Integer, nullable=True))
    op.add_column("test_sessions", sa.Column("stop_reason", sa.String(30), nullable=True))
    op.add_column("test_sessions", sa.Column("flags", JSONB, nullable=False, server_default="{}"))
    op.add_column("test_sessions", sa.Column("seed", sa.BigInteger, nullable=True))

    op.create_table(
        "test_session_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("item_key", sa.String(80), nullable=False),
        sa.Column("family_id", sa.String(40), nullable=False),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("topic", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("skills", JSONB, nullable=False, server_default="[]"),
        sa.Column("stem", sa.Text, nullable=False),
        sa.Column("code", sa.Text, nullable=True),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("options", JSONB, nullable=False),
        sa.Column("correct_index", sa.Integer, nullable=False),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("a", sa.Float, nullable=False),
        sa.Column("b", sa.Float, nullable=False),
        sa.Column("c", sa.Float, nullable=False),
        sa.Column("time_limit_s", sa.Integer, nullable=False),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answer_index", sa.Integer, nullable=True),
        sa.Column("is_correct", sa.Boolean, nullable=True),
        sa.Column("timed_out", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("excluded", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("session_id", "seq", name="uq_session_item_seq"),
    )
    op.create_index("ix_test_session_items_session", "test_session_items", ["session_id"])
    op.create_index("ix_test_session_items_key", "test_session_items", ["item_key"])

    op.create_table(
        "item_stats",
        sa.Column("item_key", sa.String(80), primary_key=True),
        sa.Column("family_id", sa.String(40), nullable=False),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("n", sa.Integer, nullable=False, server_default="0"),
        sa.Column("correct", sa.Integer, nullable=False, server_default="0"),
        sa.Column("expected", sa.Float, nullable=False, server_default="0"),
        sa.Column("variance", sa.Float, nullable=False, server_default="0"),
        sa.Column("sessions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("b_offset", sa.Float, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("z", sa.Float, nullable=False, server_default="0"),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'quarantined')", name="ck_item_stats_status"),
    )


def downgrade() -> None:
    op.drop_table("item_stats")
    op.drop_index("ix_test_session_items_key", table_name="test_session_items")
    op.drop_index("ix_test_session_items_session", table_name="test_session_items")
    op.drop_table("test_session_items")
    for col in ("seed", "flags", "stop_reason", "items_count", "theta_se", "p_upgrade", "p_pass", "engine",
                "specialization"):
        op.drop_column("test_sessions", col)
    op.drop_table("grade_confirmations")
    op.drop_index("ix_participants_specialization", table_name="participants")
    for col in ("survey_at", "work_goal", "industry", "specialization"):
        op.drop_column("participants", col)
