"""Anonymous demand: how many companies opened the card, and the median invitation band.

The count does not name a company. The band is hidden below five invitations, so one offer
cannot be read back out of it. Neither number changes the shortlist order.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessLog

VIEW_DAYS = 90
CARD_VIEW = "card_view"


def invite_band(ranges: list[tuple[int, int]], floor: int = 5) -> dict | None:
    """Median of the lower and upper ends. ``None`` until ``floor`` complete ranges."""
    clean = [(int(low), int(high)) for low, high in ranges if low and high and int(low) > 0 and int(high) > 0]
    if len(clean) < floor:
        return None

    def median(values: list[int]) -> int:
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) // 2

    return {
        "n": len(clean),
        "median_from": median([low for low, _ in clean]),
        "median_to": median([high for _, high in clean]),
    }


def view_ids_to_note(already: set[uuid.UUID], incoming: list[uuid.UUID]) -> list[uuid.UUID]:
    """One note per person per day. Repeats in the same page are dropped."""
    seen = set(already)
    out: list[uuid.UUID] = []
    for pid in incoming:
        if pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
    return out


async def note_card_views(db: AsyncSession, employer_id: uuid.UUID,
                          candidate_ids: list[uuid.UUID]) -> None:
    """Record that this company was shown these cards today. A repeat the same day is ignored."""
    ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for pid in candidate_ids:
        if pid in seen:
            continue
        seen.add(pid)
        ids.append(pid)
        if len(ids) >= 50:
            break
    if not ids:
        return
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    already = set(await db.scalars(select(AccessLog.participant_id).where(
        AccessLog.employer_id == employer_id,
        AccessLog.access_type == CARD_VIEW,
        AccessLog.participant_id.in_(ids),
        AccessLog.timestamp >= start,
    )))
    for pid in view_ids_to_note(already, ids):
        db.add(AccessLog(employer_id=employer_id, participant_id=pid, access_type=CARD_VIEW))
