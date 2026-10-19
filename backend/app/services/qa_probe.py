"""A short QA probe: a few cases, one correct program, and copies with planted defects.

The cases are data, not code. A case that the correct program rejects does not count.
The grade does not move.
"""
from __future__ import annotations

from collections.abc import Callable

CASE_LIMIT = 5

_MUTANTS: tuple[tuple[str, Callable[[int], int]], ...] = (
    ("нет нижней границы", lambda n: min(100, n)),
    ("нет верхней границы", lambda n: max(0, n)),
    ("всегда ноль", lambda n: 0),
    ("сдвиг на единицу", lambda n: max(0, min(100, n + 1))),
)


def _good(number: int) -> int:
    return max(0, min(100, number))


def judge_cases(cases: list[tuple[str, str]]) -> dict:
    """``cases`` are (input, expected). At most CASE_LIMIT pairs."""
    if len(cases) > CASE_LIMIT:
        raise ValueError("limit")
    accepted: list[tuple[int, int]] = []
    rejected = 0
    for raw_in, raw_out in cases:
        try:
            given = int(str(raw_in).strip())
            expected = int(str(raw_out).strip())
        except ValueError:
            rejected += 1
            continue
        if _good(given) != expected:
            rejected += 1
            continue
        accepted.append((given, expected))
    killed = [
        name for name, fn in _MUTANTS
        if any(fn(given) != expected for given, expected in accepted)
    ]
    return {
        "accepted": len(accepted),
        "rejected": rejected,
        "killed": killed,
        "mutants": len(_MUTANTS),
        "grade_unchanged": True,
    }
