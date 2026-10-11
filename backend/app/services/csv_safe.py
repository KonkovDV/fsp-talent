"""CSV cells that a spreadsheet will not run as a formula (OWASP CSV injection, RT-06).

A candidate's name such as =HYPERLINK("http://…") lands in the employer's export; Excel and
LibreOffice treat a cell starting with = + - @ TAB or CR as a formula. A leading apostrophe keeps it text.
"""
from __future__ import annotations

_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    if isinstance(value, str) and value.startswith(_TRIGGERS):
        return "'" + value
    return value


def safe_row(row):
    if isinstance(row, dict):
        return {k: safe_cell(v) for k, v in row.items()}
    return [safe_cell(v) for v in row]
