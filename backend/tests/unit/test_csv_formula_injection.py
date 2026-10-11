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


def test_phone_and_telegram_stay_as_they_are():
    for good in ("+79991234567", "+7 999 123-45-67", "+7 (999) 123-45-67", "@nick", "@ivan_petrov_99"):
        assert safe_cell(good) == good
    row = safe_row({"name": "Иван", "phone": "+79991234567", "telegram": "@nick", "role": "=1+1"})
    assert row == {"name": "Иван", "phone": "+79991234567", "telegram": "@nick", "role": "'=1+1"}


def test_formula_lookalikes_of_phone_and_handle_are_escaped():
    for bad in ("+7+cmd|' /C calc'!A0", "+1", "@SUM(A1)", "@nick+1", "-7 999", "+7999123456=1", '@"x"'):
        assert safe_cell(bad).startswith("'"), bad
