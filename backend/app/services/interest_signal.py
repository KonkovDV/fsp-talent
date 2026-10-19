"""A specialist can mark two companies in thirty days. The badge stays off the score.

The company sees the mark only on a card it has already opened. One mark does not
hide anyone else and does not move the list.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

LIMIT = 2
WINDOW_DAYS = 30


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def can_mark(stamps: list[datetime | None], now: datetime, limit: int = LIMIT, days: int = WINDOW_DAYS) -> bool:
    """True when another company still fits in the window. Repeat of the same company is not a stamp."""
    cutoff = _aware(now) - timedelta(days=days)
    used = sum(1 for stamp in stamps if stamp is not None and _aware(stamp) >= cutoff)
    return used < limit


def show_mark(marked: bool, opened: bool) -> bool:
    """The badge is a private note on a card the company already opened."""
    return marked and opened
