"""A candidate can stay out of one company's search and out of a subject area.

The card never says why someone is absent. The company only sees a shorter list.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.services.survey import INDUSTRIES


def refused(industries: list[str] | None, blocked: bool, industry: str | None) -> bool:
    if blocked:
        return True
    if industry and industry != "any" and industry in (industries or []):
        return True
    return False


async def _sector(db, employer_id, industry: str | None) -> str | None:
    from app.models import Employer
    sector = industry if industry in INDUSTRIES and industry != "any" else None
    if sector is None:
        stored = await db.scalar(select(Employer.industry).where(Employer.id == employer_id))
        sector = stored if stored in INDUSTRIES and stored != "any" else None
    return sector


async def shared_scope(db, employer_id, industry: str | None) -> str | None:
    """What a shared ranking may be keyed by, or None when this company's list must not be shared.

    `drop_refused` removes people who blocked the company and people who excluded its industry. Two
    companies without blocks and with the same industry get the same exclusions, so they may share a
    cached ranking keyed by that industry. A company with any block gets its own ranking.
    """
    from app.models import CandidateBlock
    blocked = await db.scalar(select(CandidateBlock.participant_id).where(
        CandidateBlock.employer_id == employer_id).limit(1))
    if blocked is not None:
        return None
    return await _sector(db, employer_id, industry) or "-"


async def drop_refused(db, ids: set[uuid.UUID], employer_id: uuid.UUID | None,
                       industry: str | None) -> set[uuid.UUID]:
    """Ids this company must not be shown. Empty when there is no company on the request."""
    if employer_id is None or not ids:
        return set()
    from app.models import CandidateBlock, Participant

    sector = await _sector(db, employer_id, industry)
    blocked = set(await db.scalars(select(CandidateBlock.participant_id).where(
        CandidateBlock.employer_id == employer_id, CandidateBlock.participant_id.in_(ids))))
    if not sector:
        return blocked
    by_sector = set(await db.scalars(select(Participant.id).where(
        Participant.id.in_(ids), Participant.excluded_industries.contains([sector]))))
    return blocked | by_sector
