"""The role × grade showcase hides small cells, so a count cannot single out a person."""
from app.services.search.pipeline import BANK_MIN, bank_cells


def test_small_cells_are_hidden_and_counts_kept():
    cells = bank_cells([("backend", "middle", 12, 4), ("security", "lead", BANK_MIN - 1, 1), (None, "junior", 9, 0)])
    assert len(cells) == 2
    shown, hidden = cells
    assert shown == {"role": "backend", "grade": "middle", "hidden": False, "candidates": 12, "tested": 4}
    assert hidden["hidden"] and hidden["candidates"] is None and hidden["tested"] is None
