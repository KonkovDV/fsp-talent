"""A wrong password counts. Five in a row close the entrance for fifteen minutes.

The minute window in Redis stays. This counter lives on the account, so a flush of the window does not reopen it.
"""
from __future__ import annotations

from datetime import datetime, timedelta

LOCK_AFTER = 5
LOCK_FOR = timedelta(minutes=15)


def still_locked(until: datetime | None, now: datetime) -> bool:
    if until is None:
        return False
    moment = until if until.tzinfo else until.replace(tzinfo=now.tzinfo)
    return moment > now


def next_failure(count: int, now: datetime) -> tuple[int, datetime | None]:
    nxt = int(count or 0) + 1
    if nxt >= LOCK_AFTER:
        return nxt, now + LOCK_FOR
    return nxt, None
