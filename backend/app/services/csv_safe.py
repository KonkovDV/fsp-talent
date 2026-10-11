"""CSV cells that a spreadsheet will not run as a formula (OWASP CSV injection, RT-06).

A candidate's name such as =HYPERLINK("http://…") lands in the employer's export; Excel and
LibreOffice treat a cell starting with = + - @ TAB or CR as a formula. A leading apostrophe keeps it text.

Two shapes that start with a trigger but cannot carry a formula stay as they are, so an ATS import gets
the real value: a phone number (+7 999 123-45-67: only digits, spaces, brackets and dashes after "+")
and a Telegram handle (@nick: letters, digits and "_"). Anything else after a trigger is escaped.
"""
from __future__ import annotations

import re

_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")
_PHONE = re.compile(r"\+\d[\d ()\-]{5,24}")          # at least 7 digits-ish, no operators but "-" between digits
_TELEGRAM = re.compile(r"@[A-Za-z0-9_]{3,32}")


def _harmless(value: str) -> bool:
    if _TELEGRAM.fullmatch(value):
        return True
    return bool(_PHONE.fullmatch(value)) and sum(ch.isdigit() for ch in value) >= 7


def safe_cell(value):
    if isinstance(value, str) and value.startswith(_TRIGGERS) and not _harmless(value):
        return "'" + value
    return value


def safe_row(row):
    if isinstance(row, dict):
        return {k: safe_cell(v) for k, v in row.items()}
    return [safe_cell(v) for v in row]
