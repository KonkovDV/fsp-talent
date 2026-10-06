"""Salary hint and anonymous market cells."""
import os

from app.services.market import quartiles, reason_shares, salary_gap_hint


def test_hint_names_the_gap_and_stays_quiet_when_the_offer_covers_it():
    assert salary_gap_hint(80_000, 100_000) == "Ваша вилка ниже ожиданий кандидата на 20 %"
    assert salary_gap_hint(120_000, 100_000) is None
    assert salary_gap_hint(80_000, None) is None


def test_quartiles_and_reasons_need_five_people():
    assert quartiles([1, 2, 3, 4]) is None
    cell = quartiles([100, 200, 300, 400, 500])
    assert cell is not None and cell["n"] == 5 and cell["p25"] <= cell["median"] <= cell["p75"]
    assert reason_shares(["salary"] * 4) is None
    shares = reason_shares(["salary"] * 3 + ["format"] * 2)
    assert shares is not None and shares["n"] == 5 and abs(sum(shares["shares"].values()) - 1) < 1e-9


def test_demo_seed_refuses_production(monkeypatch):
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
