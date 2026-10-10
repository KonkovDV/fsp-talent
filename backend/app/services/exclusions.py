"""A candidate can stay out of one company's search and out of a subject area.

The card never says why someone is absent. The company only sees a shorter list.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select


def refused(industries: list[str] | None, blocked: bool, industry: str | None) -> bool:
    if blocked:
        return True
    if industry and industry != "any" and industry in (industries or []):
        return True
    return False


async def drop_refused(db, ids: set[uuid.UUID], employer_id: uuid.UUID | None,
                       industry: str | None) -> set[uuid.UUID]:
    """Ids this company must not be shown. Empty when there is no company on the request."""
    if employer_id is None or not ids:
        return set()
    from app.models import CandidateBlock, Employer, Participant

    sector = industry if industry and industry != "any" else None
    if sector is None:
        sector = await db.scalar(select(Employer.industry).where(Employer.id == employer_id))
        if sector == "any":
            sector = None
    blocked = set(await db.scalars(select(CandidateBlock.participant_id).where(
        CandidateBlock.employer_id == employer_id, CandidateBlock.participant_id.in_(ids))))
    if not sector:
        return blocked
    by_sector = set(await db.scalars(select(Participant.id).where(
        Participant.id.in_(ids), Participant.excluded_industries.contains([sector]))))
    return blocked | by_sector
