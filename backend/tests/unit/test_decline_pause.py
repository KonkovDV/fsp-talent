"""After a decline the same company waits 30 days before inviting the same person again."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.offers import DECLINE_PAUSE, reinvite_after

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


def _declined(days_ago: int | None, created_days_ago: int = 40):
    return SimpleNamespace(responded_at=None if days_ago is None else NOW - timedelta(days=days_ago),
                           created_at=NOW - timedelta(days=created_days_ago))


def test_pause_runs_thirty_days_from_the_answer():
    assert reinvite_after([_declined(3)], NOW) == NOW - timedelta(days=3) + DECLINE_PAUSE
    assert reinvite_after([_declined(31)], NOW) is None
    assert reinvite_after([], NOW) is None


def test_old_rows_fall_back_to_the_invitation_date():
    assert reinvite_after([_declined(None, created_days_ago=10)], NOW) == NOW + timedelta(days=20)
    assert reinvite_after([_declined(None, created_days_ago=45), _declined(5)], NOW) == NOW + timedelta(days=25)
