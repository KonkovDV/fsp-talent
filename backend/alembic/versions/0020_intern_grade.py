"""Intern grade: the step below junior, for candidates looking for an internship.

Revision ID: 0020_intern_grade
Revises: 0019_skill_confirmed_at
"""
from __future__ import annotations

from alembic import op

revision = "0020_intern_grade"
down_revision = "0019_skill_confirmed_at"
branch_labels = None
depends_on = None

_WIDE = "('intern', 'junior', 'middle', 'senior', 'lead')"
_NARROW = "('junior', 'middle', 'senior', 'lead')"


def _replace(table: str, name: str, expression: str) -> None:
    op.drop_constraint(name, table, type_="check")
    op.create_check_constraint(name, table, expression)


def upgrade() -> None:
    _replace("test_questions", "ck_question_grade", f"target_grade IN {_WIDE}")
    _replace("test_sessions", "ck_session_grade", f"target_grade IN {_WIDE}")
    _replace("grade_confirmations", "ck_grade_confirmation_grade", f"grade IN {_WIDE}")
    _replace("participants", "ck_participants_assessed_grade",
             f"assessed_grade IS NULL OR assessed_grade IN {_WIDE}")


def downgrade() -> None:
    op.execute("UPDATE test_questions SET target_grade = 'junior' WHERE target_grade = 'intern'")
    op.execute("UPDATE test_sessions SET target_grade = 'junior' WHERE target_grade = 'intern'")
    op.execute("UPDATE grade_confirmations SET grade = 'junior' WHERE grade = 'intern'")
    op.execute("UPDATE participants SET assessed_grade = 'junior' WHERE assessed_grade = 'intern'")
    op.execute("UPDATE participants SET declared_grade = 'junior' WHERE declared_grade = 'intern'")
    _replace("test_questions", "ck_question_grade", f"target_grade IN {_NARROW}")
    _replace("test_sessions", "ck_session_grade", f"target_grade IN {_NARROW}")
    _replace("grade_confirmations", "ck_grade_confirmation_grade", f"grade IN {_NARROW}")
    _replace("participants", "ck_participants_assessed_grade",
             f"assessed_grade IS NULL OR assessed_grade IN {_NARROW}")
