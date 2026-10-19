"""Offer expiry on the request path.

Celery marks stale pending offers once an hour. The API must not wait for that:
a pending row past expires_at still blocks a new offer and still looks active in lists.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.offer_flow import move_offer

DECLINE_PAUSE = timedelta(days=30)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=UTC)


def expire_if_stale(offer, now: datetime | None = None) -> bool:
    """Set status to expired when a pending offer is past expires_at. Returns True if it changed."""
    if offer.status != "pending":
        return False
    expires = _aware(offer.expires_at)
    if expires is None or expires >= (now or datetime.now(UTC)):
        return False
    move_offer(offer, "expired")
    return True


def expire_stale(offers, now: datetime | None = None) -> bool:
    """Expire every stale pending offer. A short-circuit any() would leave the rest pending."""
    changed = False
    for offer in offers:
        if expire_if_stale(offer, now):
            changed = True
    return changed


def reinvite_after(declined, now: datetime | None = None) -> datetime | None:
    """When the company may invite the person again after their declines; None means now.

    A decline is the candidate's answer: the same company waits 30 days before asking again. The pause runs
    from the answer, or from the invitation itself for rows that predate the answer time.
    """
    now = now or datetime.now(UTC)
    ends = [(_aware(o.responded_at) or _aware(o.created_at)) + DECLINE_PAUSE for o in declined
            if (_aware(o.responded_at) or _aware(o.created_at)) is not None]
    latest = max(ends, default=None)
    return latest if latest and latest > now else None
