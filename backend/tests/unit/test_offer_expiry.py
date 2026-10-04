from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.offers import expire_if_stale, expire_stale


def _offer(status="pending", expires_at=None):
    return SimpleNamespace(status=status, expires_at=expires_at)


def test_pending_past_due_becomes_expired():
    offer = _offer(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    assert expire_if_stale(offer) is True
    assert offer.status == "expired"


def test_fresh_pending_and_terminal_states_stay():
    fresh = _offer(expires_at=datetime.now(UTC) + timedelta(days=1))
    assert expire_if_stale(fresh) is False
    assert fresh.status == "pending"
    accepted = _offer(status="accepted", expires_at=datetime.now(UTC) - timedelta(days=1))
    assert expire_if_stale(accepted) is False
    assert accepted.status == "accepted"
    naive = _offer(expires_at=datetime.now() - timedelta(days=2))
    assert expire_if_stale(naive) is True


def test_every_stale_offer_expires_not_only_the_first():
    now = datetime.now(UTC)
    rows = [
        _offer(expires_at=now - timedelta(days=1)),
        _offer(expires_at=now - timedelta(days=2)),
        _offer(expires_at=now + timedelta(days=1)),
        _offer(expires_at=now - timedelta(days=3)),
    ]
    assert expire_stale(rows, now) is True
    assert [row.status for row in rows] == ["expired", "expired", "pending", "expired"]
