"""The role × grade showcase hides small cells, so a count cannot single out a person."""
from datetime import UTC, datetime, timedelta

from app.services.matching import recommended_categories
from app.services.search.pipeline import BANK_MIN, bank_cells, created_after


def test_small_cells_are_hidden_and_counts_kept():
    cells = bank_cells([("backend", "middle", 12, 6), ("security", "lead", BANK_MIN - 1, 1), (None, "junior", 9, 0)])
    assert len(cells) == 2
    shown, hidden = cells
    assert shown == {"role": "backend", "grade": "middle", "hidden": False, "candidates": 12, "tested": 6}
    assert hidden["hidden"] and hidden["candidates"] is None and hidden["tested"] is None


def test_recommended_chip_skips_a_cell_under_five():
    rows = [("backend", "senior", 0.7)] * 6 + [("qa", "intern", 0.99)] * 4
    cells = recommended_categories(rows, min_n=BANK_MIN)
    assert cells == [{"role": "backend", "grade": "senior", "candidates": 6, "best": 0.7}]


def test_fresh_window_is_fourteen_days_when_asked():
    now = datetime(2026, 10, 8, tzinfo=UTC)
    assert created_after(now, None) is None
    assert created_after(now, 14) == now - timedelta(days=14)


def test_a_small_tested_count_is_not_shown():
    """SEC3-10: embedded/middle 7 people, 2 tested — the 2 (and the 5 untested next to it) single out people."""
    few_tested, few_untested, both = bank_cells([("embedded", "middle", 7, 2), ("embedded", "junior", 9, 5),
                                                 ("backend", "middle", 10, 5)])
    assert few_tested["candidates"] == 7 and few_tested["tested"] is None
    assert few_untested["candidates"] == 9 and few_untested["tested"] is None
    assert both["tested"] == 5
