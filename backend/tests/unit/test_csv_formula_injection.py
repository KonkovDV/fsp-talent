"""RT-06: a name like =HYPERLINK(...) must reach the CSV export as text, not a formula."""
import csv
import io

from app.services.csv_safe import safe_cell, safe_row
from app.services.desk import complaints_csv


def test_formula_triggers_are_neutralised():
    for bad in ('=HYPERLINK("http://evil","x")', "+1", "-2+3", "@SUM(A1)", "\t=1", "\r=1"):
        assert safe_cell(bad).startswith("'")


def test_plain_values_untouched():
    assert safe_cell("Иван") == "Иван"
    assert safe_cell(5) == 5
    assert safe_cell(None) is None
    assert safe_row({"a": "=1", "b": "ok"}) == {"a": "'=1", "b": "ok"}


def test_complaints_csv_is_safe():
    out = complaints_csv([{"id": "1", "reason": "=cmd|' /C calc'!A0", "created_at": "t"}])
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[1][1].startswith("'=")
