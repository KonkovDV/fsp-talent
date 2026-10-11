"""Hourly delta of the FSP registry: only linked profiles, only new protocol lines."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Participant
from app.services.fsp.mock import FSPAdapter
from app.services.profile import rebuild_profile, reconcile_results

CURSOR = "fsp:changes:since"


async def pull_registry_changes(db: AsyncSession, redis, adapter: FSPAdapter) -> tuple[int, datetime]:
    """Read ids changed since the stored cursor and reconcile their protocol lines with the registry.

    The first run looks back two hours, then the cursor moves to the registry's `next_since`.
    """
    raw = await redis.get(CURSOR)
    since = datetime.fromisoformat(raw) if raw else datetime.now(UTC) - timedelta(hours=2)
    page = await adapter.changes_since(since)
    updated = 0
    if page.fsp_ids:
        people = list(await db.scalars(select(Participant).where(
            Participant.fsp_id.in_(page.fsp_ids), Participant.deleted_at.is_(None))))
        for person in people:
            data = await adapter.fetch_participant(person.fsp_id or "")
            if data is None:
                continue
            # Annulled and corrected lines are applied too, not only new ones (audit M-3).
            if any((await reconcile_results(db, person, data)).values()):
                await rebuild_profile(db, person)
                updated += 1
    return updated, page.next_since


async def remember_cursor(redis, nxt: datetime | None) -> None:
    """Move the cursor only after the database commit succeeded."""
    if nxt is not None:
        await redis.set(CURSOR, nxt.isoformat())
