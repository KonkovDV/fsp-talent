from datetime import UTC, datetime, timedelta

from app.services.login_lock import next_failure, still_locked

NOW = datetime(2026, 10, 10, tzinfo=UTC)


def test_five_wrong_passwords_close_the_entrance():
    count, until = next_failure(3, NOW)
    assert count == 4 and until is None
    count, until = next_failure(4, NOW)
    assert count == 5 and until == NOW + timedelta(minutes=15)
    assert still_locked(until, NOW + timedelta(minutes=1))
    assert not still_locked(until, NOW + timedelta(minutes=16))
    assert not still_locked(None, NOW)
