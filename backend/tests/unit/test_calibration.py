from datetime import UTC, datetime, timedelta

from app.services.assessment import calibration_open, calibration_until

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


def test_the_window_is_one_day_and_then_the_ordinary_locks_apply():
    opened = NOW - timedelta(hours=23)
    assert calibration_open(opened, NOW) is True
    assert calibration_until(opened) == opened + timedelta(hours=24)
    assert calibration_open(NOW - timedelta(hours=25), NOW) is False
    assert calibration_open(None, NOW) is False
