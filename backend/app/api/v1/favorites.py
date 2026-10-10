"""A company's favorites: anonymous cards kept apart from any need.

The list shows only people who are still in search, with the same card the search shows.
Someone who hid the profile, set «не ищу» or deleted the account drops out of the list
and is counted, not named. Only the company that saved a card sees the row.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.core.database import get_db
from app.models import CandidateInterest, Employer, EmployerFavorite, Participant
from app.models.favorite import FAVORITES_MAX
from app.services.hiring_practice import sees_senior
from app.services.search.pipeline import _build_cards, visible_in_search

router = APIRouter(prefix="/employer/favorites", tags=["employer"])


async def _visible(db: AsyncSession, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    rows = await db.scalars(select(Participant.id).where(Participant.id.in_(ids), visible_in_search()))
    return set(rows)


@router.get("")
async def list_favorites(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    employer_id = uuid.UUID(current["sub"])
    rows = list(await db.scalars(
        select(EmployerFavorite).where(EmployerFavorite.employer_id == employer_id)
        .order_by(EmployerFavorite.created_at.desc())))
    ids = [row.participant_id for row in rows]
    shown = await _visible(db, ids)
    ordered = [pid for pid in ids if pid in shown]
    company = await db.get(Employer, employer_id)
    full_card = sees_senior(company.hiring_practice if company is not None else None)
    cards = await _build_cards(db, ordered, set(), {}, set(), None, full_card=full_card) if ordered else []
    saved = {row.participant_id: row.created_at for row in rows}
    status = {row.participant_id: row.interest for row in rows}
    returned = set(await db.scalars(select(CandidateInterest.participant_id).where(
        CandidateInterest.employer_id == employer_id,
        CandidateInterest.participant_id.in_(ordered)))) if ordered else set()
    for card in cards:
        pid = uuid.UUID(card["candidate_id"])
        card["saved_at"] = saved[pid].isoformat()
        card["interest"] = status.get(pid, "saved")
        card["returned_interest"] = pid in returned
    return {"items": cards, "ids": [str(pid) for pid in ordered], "hidden": len(ids) - len(ordered),
            "max": FAVORITES_MAX}


@router.post("/{participant_id}", status_code=201)
async def add_favorite(participant_id: uuid.UUID, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    employer_id = uuid.UUID(current["sub"])
    if participant_id not in await _visible(db, [participant_id]):
        raise ApiError(404, "not_found", "Кандидат не найден в поиске")
    existing = await db.scalar(select(EmployerFavorite.id).where(
        EmployerFavorite.employer_id == employer_id, EmployerFavorite.participant_id == participant_id))
    if existing is None:
        count = await db.scalar(select(func.count()).select_from(EmployerFavorite).where(
            EmployerFavorite.employer_id == employer_id))
        if (count or 0) >= FAVORITES_MAX:
            raise ApiError(409, "conflict", f"В избранном уже {FAVORITES_MAX} карточек: уберите лишние")
        db.add(EmployerFavorite(employer_id=employer_id, participant_id=participant_id, created_at=datetime.now(UTC)))
        await db.commit()
    return {"candidate_id": str(participant_id), "favorite": True}


class InterestIn(BaseModel):
    interest: Literal["saved", "priority"]


@router.put("/{participant_id}")
async def set_interest(participant_id: uuid.UUID, body: InterestIn, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    """Priority is a label on the anonymous card. It does not change the match score."""
    row = await db.scalar(select(EmployerFavorite).where(
        EmployerFavorite.employer_id == uuid.UUID(current["sub"]), EmployerFavorite.participant_id == participant_id))
    if row is None:
        raise ApiError(404, "not_found", "Карточки нет в избранном")
    row.interest = body.interest
    await db.commit()
    return {"candidate_id": str(participant_id), "interest": row.interest}


@router.delete("/{participant_id}")
async def remove_favorite(participant_id: uuid.UUID, current: dict = Depends(get_current_employer),
                          db: AsyncSession = Depends(get_db)):
    await db.execute(delete(EmployerFavorite).where(
        EmployerFavorite.employer_id == uuid.UUID(current["sub"]), EmployerFavorite.participant_id == participant_id))
    await db.commit()
    return {"candidate_id": str(participant_id), "favorite": False}
