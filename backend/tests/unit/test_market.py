"""Salary hint and anonymous market cells."""
import os
from datetime import UTC, datetime, timedelta

from app.services.market import (
    fork_span,
    offer_pulse,
    quartiles,
    reason_shares,
    reply_hours,
    salary_band,
    salary_gap_hint,
)


def test_hint_names_the_gap_and_stays_quiet_when_the_offer_covers_it():
    assert salary_gap_hint(80_000, 100_000) == "Ваша вилка ниже ожиданий кандидата (ориентир от 100 000 ₽)"
    assert salary_gap_hint(80_000, 149_000) == salary_gap_hint(80_000, 100_000)
    assert salary_gap_hint(120_000, 100_000) is None
    assert salary_gap_hint(45_000, 40_000) is None
    assert salary_gap_hint(80_000, None) is None


def test_quartiles_and_reasons_need_five_people():
    assert quartiles([1, 2, 3, 4]) is None
    cell = quartiles([100, 200, 300, 400, 500])
    assert cell is not None and cell["n"] == 5 and cell["p25"] <= cell["median"] <= cell["p75"]
    assert reason_shares(["salary"] * 4) is None
    shares = reason_shares(["salary"] * 3 + ["format"] * 2)
    assert shares is not None and shares["n"] == 5 and abs(sum(shares["shares"].values()) - 1) < 1e-9


def test_a_wish_is_placed_only_when_the_cell_is_shown():
    cell = {"p25": 200, "median": 300, "p75": 400, "n": 5}
    assert salary_band(100, cell) == "below_p25"
    assert salary_band(200, cell) == "below_median"
    assert salary_band(300, cell) == "through_p75"
    assert salary_band(400, cell) == "through_p75"
    assert salary_band(401, cell) == "above_p75"
    assert salary_band(None, cell) is None
    assert salary_band(250, None) is None


def test_demo_seed_refuses_production(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setenv("ENV", "production")
    from seed.generate_seed import _refuse_production
    try:
        _refuse_production()
    except SystemExit as e:
        assert "production" in str(e)
    else:
        raise AssertionError("seed must refuse production")
    monkeypatch.setenv("ENV", "")
    os.environ.pop("ENV", None)
    _refuse_production()


def test_a_fork_wider_than_three_and_a_half_only_warns():
    assert fork_span(100_000, 350_000) is None
    assert fork_span(100_000, 350_001) == "wide"
    assert fork_span(None, 400_000) is None
    assert fork_span(200_000, 100_000) is None


def test_own_invites_compare_this_window_with_the_previous_one():
    now = datetime(2026, 10, 19, tzinfo=UTC)
    rows = [
        (now - timedelta(days=2), "accepted", now - timedelta(days=1)),
        (now - timedelta(days=40), "expired", None),
        (now - timedelta(days=10), "pending", None),
    ]
    pulse = offer_pulse(rows, now)
    assert pulse["current"] == {"sent": 2, "viewed": 1, "accepted": 1, "declined": 0, "expired": 0}
    assert pulse["previous"] == {"sent": 1, "viewed": 0, "accepted": 0, "declined": 0, "expired": 1}


def test_reply_time_stays_hidden_below_five_answers():
    start = datetime(2026, 10, 1, tzinfo=UTC)
    spans = [(start, start + timedelta(hours=h)) for h in (2, 4, 6, 8)]
    assert reply_hours(spans) is None
    spans.append((start, start + timedelta(hours=10)))
    shown = reply_hours(spans)
    assert shown is not None and shown["n"] == 5 and shown["median_hours"] == 6.0
    assert reply_hours([(start, start - timedelta(hours=1))] * 5) is None
    mixed = reply_hours([(start.replace(tzinfo=None), start + timedelta(hours=2))] * 5)
    assert mixed is not None and mixed["median_hours"] == 2.0
