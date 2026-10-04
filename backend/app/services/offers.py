"""Offer expiry on the request path.

Celery marks stale pending offers once an hour. The API must not wait for that:
a pending row past expires_at still blocks a new offer and still looks active in lists.
"""
from __future__ import annotations

from datetime import UTC, datetime


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
    offer.status = "expired"
    return True


def expire_stale(offers, now: datetime | None = None) -> bool:
    """Expire every stale pending offer. A short-circuit any() would leave the rest pending."""
    changed = False
    for offer in offers:
        if expire_if_stale(offer, now):
            changed = True
    return changed
