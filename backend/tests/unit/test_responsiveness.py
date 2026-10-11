"""CM-16: does the company open applications? A fact for the candidate, hidden under five cases."""
from datetime import UTC, datetime, timedelta

from app.services.matching import wilson_lower
from app.services.reputation import MIN_N, acceptance, responsiveness

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


def _app(days_ago: float, opened_after: float | None):
    made = NOW - timedelta(days=days_ago)
    return made, (made + timedelta(days=opened_after)) if opened_after is not None else None


def test_responsiveness_under_five_applications_is_hidden():
    out = responsiveness([_app(20, 1), _app(20, 2), _app(30, None), _app(40, 3)], NOW)
    assert out["shown"] is False and out["n"] == 4 and out["note"] == "мало данных"
    assert "median_days" not in out and "lower" not in out


def test_responsiveness_three_of_five_within_seven_days():
    apps = [_app(30, 1), _app(30, 2), _app(30, 6.5), _app(30, 12), _app(30, None)]
    out = responsiveness(apps, NOW)
    assert out["shown"] is True and out["n"] == 5 and out["count"] == 3
    assert out["count"] / out["n"] == 0.6
    assert out["lower"] == round(wilson_lower(3, 5, z=1.64), 3)
    assert out["median_days"] == 4.2  # opened ones: 1, 2, 6.5, 12 → median 4.25 → 4.2 (banker's rounding)
    assert out["window_days"] == 90 and out["within_days"] == 7


def test_responsiveness_does_not_count_fresh_unopened_or_old_applications():
    apps = [_app(2, None)] * 3 + [_app(120, 1)] * 3 + [_app(10, 1)] * MIN_N
    out = responsiveness(apps, NOW)
    assert out["n"] == MIN_N and out["count"] == MIN_N


def test_responsiveness_fresh_application_opened_counts():
    out = responsiveness([_app(1, 0.5)] * MIN_N, NOW)
    assert out["n"] == MIN_N and out["count"] == MIN_N and out["median_days"] == 0.5


def test_responsiveness_acceptance_counts_answered_invitations_only():
    out = acceptance(["accepted", "accepted", "rejected", "pending", "expired", "withdrawn", "accepted", "rejected"])
    assert out["n"] == 5 and out["count"] == 3
    assert acceptance(["accepted", "pending"])["shown"] is False
