"""unique (participant_id, event_id) on results

Revision ID: 0007_result_participant_event
Revises: 0006_vacancy_updated_at
Create Date: 2026-10-04

The Result ORM constraint was added in 2fc7060. Without this index the
database still accepts two rows for the same event.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007_result_participant_event"
down_revision: Union[str, Sequence[str], None] = "0006_vacancy_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_result_participant_event",
        "results",
        ["participant_id", "event_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_result_participant_event", "results", type_="unique")
