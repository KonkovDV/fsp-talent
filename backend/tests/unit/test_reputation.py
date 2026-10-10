from datetime import UTC, datetime, timedelta

from app.services.reputation import rate, summarize

NOW = datetime(2026, 10, 10, tzinfo=UTC)


def test_under_five_cases_the_rate_stays_hidden():
    assert rate(4, 4) == {"shown": False, "n": 4, "note": "мало данных"}


def test_five_cases_publish_the_lower_bound_not_the_raw_share():
    shown = rate(5, 5)
    assert shown["shown"] is True and shown["lower"] < 1


def test_summary_keeps_tenure_even_when_the_rates_are_hidden():
    facts = summarize(accepted=1, replied=1, interviewed=0, offers=2, complaints=0,
                      created_at=NOW - timedelta(days=40), now=NOW)
    assert facts["tenure_days"] == 40
    assert facts["reply"]["shown"] is False and facts["complaints"]["shown"] is False
    assert summarize(accepted=0, replied=0, interviewed=0, offers=0, complaints=0,
                     created_at=None, now=NOW)["tenure_days"] is None
