"""Wrong-password throttling without an account lockout anyone can trigger (stand audit I-01).

Five wrong passwords used to lock the account for everyone for fifteen minutes. The jury addresses are
published, so any visitor could lock jury1. Now (OWASP ASVS 5.0 V6.3, NIST SP 800-63B §5.2.2):

* five wrong passwords from one address close the entrance for that address and that account only, for
  fifteen minutes (a Redis counter per account × IP);
* the account itself is locked only after ACCOUNT_LOCK_AFTER consecutive failures from all addresses —
  NIST caps this at 100 — and the published demo accounts are never locked as a whole;
* the minute window per account × IP and per IP stays in front (auth._login).
"""
from __future__ import annotations

from datetime import datetime, timedelta

PAIR_LOCK_AFTER = 5
LOCK_FOR = timedelta(minutes=15)
ACCOUNT_LOCK_AFTER = 100
# Kept for old imports: the per-address threshold.
LOCK_AFTER = PAIR_LOCK_AFTER


def still_locked(until: datetime | None, now: datetime) -> bool:
    if until is None:
        return False
    moment = until if until.tzinfo else until.replace(tzinfo=now.tzinfo)
    return moment > now


def next_failure(count: int, now: datetime, *, lockable: bool = True) -> tuple[int, datetime | None]:
    """The account-wide counter. Locks only after ACCOUNT_LOCK_AFTER, and never a published demo account."""
    nxt = int(count or 0) + 1
    if lockable and nxt >= ACCOUNT_LOCK_AFTER:
        return nxt, now + LOCK_FOR
    return nxt, None


def demo_protected(email: str, suffixes: str, demo_mode: bool) -> bool:
    """A published demo address on a demo stand: shared by the jury, never locked as a whole."""
    if not demo_mode:
        return False
    return any(email.endswith(s.strip()) for s in suffixes.split(",") if s.strip())


def pair_key(role: str, email: str, ip: str) -> str:
    return f"auth:fail:{role}:{email}:{ip}"


async def pair_locked(redis, key: str) -> bool:
    try:
        return int(await redis.get(key) or 0) >= PAIR_LOCK_AFTER
    except Exception:  # noqa: BLE001 - the minute windows in front are fail-closed already
        return False


async def pair_failed(redis, key: str) -> None:
    try:
        pipe = redis.pipeline(transaction=False)
        pipe.incr(key)
        pipe.expire(key, int(LOCK_FOR.total_seconds()))
        await pipe.execute()
    except Exception:  # noqa: BLE001
        return


async def pair_cleared(redis, key: str) -> None:
    try:
        await redis.delete(key)
    except Exception:  # noqa: BLE001
        return
