"""Salary hint before an invitation, and anonymous market figures.

A hint never blocks the invitation. Quartiles and decline shares are shown only when at least
MIN_CELL people sit in the cell, so one person cannot be picked out of the number.
"""
from __future__ import annotations

import statistics
from datetime import UTC, timedelta

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
    """Say the offer is short only when it is under the whole 50 000 ₽ band of the ask.

    Inside the band the answer stays quiet. A sweep then learns the band, not the ruble,
    and an offer that already covers a small ask is not called short.
    """
    if not expected_from or expected_from <= 0 or offer_to <= 0:
        return None
    low = (expected_from // 50_000) * 50_000
    if low == 0 or offer_to >= low:
        return None
    shown = f"{low:,}".replace(",", " ")
    return f"Ваша вилка ниже ожиданий кандидата (ориентир от {shown} ₽)"


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


WIDE_FORK = 3.5


def fork_span(salary_from: int | None, salary_to: int | None) -> str | None:
    """A fork wider than three and a half times warns. It never blocks and never changes rank."""
    if not salary_from or not salary_to or salary_from <= 0 or salary_to < salary_from:
        return None
    if salary_to > salary_from * WIDE_FORK:
        return "wide"
    return None


def offer_pulse(rows: list[tuple], now, days: int = 30) -> dict:
    """This company's own invitations, this window against the one before it.

    The counts are the company's own acts, so a small number stays on the page.
    """
    now = _aware(now)

    def bucket(start, end) -> dict:
        sent = viewed = accepted = declined = expired = 0
        for created, status, seen in rows:
            created = _aware(created)
            if created is None or not (start <= created < end):
                continue
            sent += 1
            if seen is not None or status in {"accepted", "rejected"}:
                viewed += 1
            if status == "accepted":
                accepted += 1
            elif status == "rejected":
                declined += 1
            elif status == "expired":
                expired += 1
        return {"sent": sent, "viewed": viewed, "accepted": accepted,
                "declined": declined, "expired": expired}

    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)
    return {"days": days, "current": bucket(current_start, now + timedelta(seconds=1)),
            "previous": bucket(previous_start, current_start)}


def market_flag(salary_from: int | None, salary_to: int | None, median: int | None) -> str | None:
    """A fork far from the category median. Nothing when the cell has no published median.

    below_market: the top of the fork is under half the median.
    suspicious: the bottom is over three times the median.
    A valid fork cannot be both. The flag warns and never blocks.
    """
    if not median or median <= 0:
        return None
    if salary_from and salary_from > median * 3:
        return "suspicious"
    if salary_to and salary_to * 2 < median:
        return "below_market"
    return None


async def role_median(db, role: str | None, grade: str | None) -> int | None:
    """Median expectation in one role × grade cell. Hidden below MIN_CELL, same rule as the market page."""
    if not role or not grade:
        return None
    from sqlalchemy import select

    from app.models import CategoryAssignment, Participant

    amounts = list(await db.scalars(
        select(Participant.salary_from_gross)
        .join(CategoryAssignment, CategoryAssignment.participant_id == Participant.id)
        .where(CategoryAssignment.primary_role == role, CategoryAssignment.grade == grade,
               Participant.salary_from_gross.is_not(None), Participant.deleted_at.is_(None),
               Participant.is_visible.is_(True))))
    cell = quartiles([int(amount) for amount in amounts if amount])
    return cell["median"] if cell else None


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


def _aware(moment):
    if moment is None:
        return None
    return moment if getattr(moment, "tzinfo", None) else moment.replace(tzinfo=UTC)


def reply_hours(spans: list[tuple], floor: int = MIN_CELL) -> dict | None:
    """Median hours from the invitation to the answer. Hidden below five answers."""
    hours = []
    for start, end in spans:
        start, end = _aware(start), _aware(end)
        if start is None or end is None:
            continue
        delta = (end - start).total_seconds() / 3600
        if delta >= 0:
            hours.append(delta)
    if len(hours) < floor:
        return None
    return {"n": len(hours), "median_hours": round(statistics.median(hours), 1)}


def own_reason_counts(reasons: list[str | None]) -> dict | None:
    """Counts of this company's own refusals. Each one was already on that invitation."""
    named = [reason for reason in reasons if reason in DECLINE_LABELS]
    if not named:
        return None
    counts = {code: named.count(code) for code in DECLINE_REASONS if named.count(code)}
    return {"n": len(named), "counts": counts}
