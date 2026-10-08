"""Salary hint before an invitation, and anonymous market figures.

A hint never blocks the invitation. Quartiles and decline shares are shown only when at least
MIN_CELL people sit in the cell, so one person cannot be picked out of the number.
"""
from __future__ import annotations

DECLINE_REASONS = ("salary", "format", "stack", "not_looking", "other")
DECLINE_LABELS = {
    "salary": "Зарплата",
    "format": "Формат работы",
    "stack": "Стек",
    "not_looking": "Сейчас не ищу",
    "other": "Другое",
}
MIN_CELL = 5


def salary_gap_hint(offer_to: int, expected_from: int | None) -> str | None:
    """Russian sentence when the offer's top is below what the candidate asked, else None."""
    if not expected_from or expected_from <= 0 or offer_to >= expected_from:
        return None
    pct = round(100 * (expected_from - offer_to) / expected_from)
    if pct <= 0:
        return None
    return f"Ваша вилка ниже ожиданий кандидата на {pct} %"


def quartiles(values: list[int]) -> dict | None:
    if len(values) < MIN_CELL:
        return None
    ordered = sorted(values)

    def at(p: float) -> int:
        pos = (len(ordered) - 1) * p
        lo = int(pos)
        hi = min(lo + 1, len(ordered) - 1)
        return round(ordered[lo] * (1 - (pos - lo)) + ordered[hi] * (pos - lo))

    return {"p25": at(0.25), "median": at(0.5), "p75": at(0.75), "n": len(ordered)}


def salary_band(mine: int | None, cell: dict | None) -> str | None:
    """Where one wish sits on a quartile cell. Missing wish or a hidden cell gives nothing to compare."""
    if mine is None or mine <= 0 or not cell:
        return None
    if mine < cell["p25"]:
        return "below_p25"
    if mine < cell["median"]:
        return "below_median"
    if mine <= cell["p75"]:
        return "through_p75"
    return "above_p75"


def reason_shares(reasons: list[str | None]) -> dict | None:
    """Shares of decline reasons. Hidden until MIN_CELL answers, so a single refusal stays private."""
    named = [r for r in reasons if r in DECLINE_LABELS]
    if len(named) < MIN_CELL:
        return None
    counts = {code: named.count(code) for code in DECLINE_REASONS}
    total = len(named)
    return {"n": total, "shares": {code: round(counts[code] / total, 3) for code in DECLINE_REASONS if counts[code]}}
