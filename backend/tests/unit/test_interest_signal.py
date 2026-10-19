"""Two company marks in thirty days, and the badge only on a card already opened."""
from datetime import UTC, datetime, timedelta

from app.services.interest_signal import can_mark, show_mark


def test_two_fresh_marks_leave_no_room_for_a_third():
    now = datetime(2026, 10, 19, tzinfo=UTC)
    fresh = [now - timedelta(days=1), now - timedelta(days=10)]
    assert can_mark(fresh, now) is False
    assert can_mark(fresh[:1], now) is True
    older = [now - timedelta(days=31), now - timedelta(days=2)]
    assert can_mark(older, now) is True
    assert can_mark([None, now - timedelta(days=1)], now) is True


def test_the_badge_stays_off_until_the_card_was_opened():
    assert show_mark(True, False) is False
    assert show_mark(False, True) is False
    assert show_mark(True, True) is True
