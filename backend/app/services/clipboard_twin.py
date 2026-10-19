"""A copied task is a twin: one number differs from the screen.

The answer to that number is a mark for a later look. It does not change the grade.
"""
from __future__ import annotations

import hashlib
import re

_NUMBER = re.compile(r"(?<!\d)(\d{1,6})(?!\d)")


def _year(text: str) -> bool:
    if len(text) != 4 or not text.isdigit():
        return False
    return 1990 <= int(text) <= 2035


def _shift(old: str, salt: str, forbid: str | None = None) -> str:
    """A nearby integer that is neither the number on the screen nor the answer key."""
    number = int(old)
    step = 1 if int(hashlib.sha256(f"{salt}|step".encode()).hexdigest(), 16) % 2 == 0 else -1
    banned = {number}
    text = (forbid or "").strip()
    if text.isdigit():
        banned.add(int(text))
    for delta in (step, -step, 2 * step, -2 * step, 3, -3, 4, -4):
        nxt = number + delta
        if nxt >= 0 and nxt not in banned:
            return str(nxt)
    nxt = number + 1
    while nxt in banned:
        nxt += 1
    return str(nxt)


def one_number_twin(text: str, salt: str, forbid: str | None = None) -> tuple[str, str, str] | None:
    """Twin text, the number on the screen, and the number that replaces it."""
    found = [match for match in _NUMBER.finditer(text) if not _year(match.group(1))]
    if not found:
        return None
    pick = int(hashlib.sha256(salt.encode()).hexdigest(), 16) % len(found)
    match = found[pick]
    old = match.group(1)
    new = _shift(old, salt, forbid)
    twin = text[: match.start(1)] + new + text[match.end(1) :]
    return twin, old, new


def copy_text(stem: str, code: str | None, salt: str, key: str | None = None) -> str | None:
    source = stem if not code else f"{stem}\n{code}"
    found = one_number_twin(source, salt, key)
    return found[0] if found else None


def twin_hit(stem: str, code: str | None, salt: str, answer: str, correct: str) -> bool:
    """True when the answer is the hidden number and not the key of the task on the screen."""
    found = one_number_twin(stem if not code else f"{stem}\n{code}", salt, correct)
    if found is None:
        return False
    _twin, _old, new = found
    given = answer.strip()
    key = correct.strip()
    return bool(given) and given == new and given != key
