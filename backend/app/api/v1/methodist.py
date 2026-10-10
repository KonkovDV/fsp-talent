"""The methodist desk: drafts stay on the moderation routes, quarantine is released here.

The flag is not writable through the API. A methodist with a second factor still has to unlock it.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.api.v1.moderation import _staff
from app.core.database import get_db
from app.models import ItemStat, MethodistLog

router = APIRouter(prefix="/methodist", tags=["methodist"])


class ReleaseIn(BaseModel):
    note: str = Field(min_length=3, max_length=500)


@router.get("")
async def me(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    employer = await _staff(current, db)
    return {"methodist": True, "email": employer.email}


@router.get("/quarantine")
async def quarantine(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    await _staff(current, db)
    rows = list(await db.scalars(select(ItemStat).where(ItemStat.status == "quarantined")
                                 .order_by(ItemStat.quarantined_at.desc()).limit(100)))
    return [{
        "item_key": row.item_key, "family_id": row.family_id, "level": row.level,
        "z": round(row.z, 2), "n": row.n,
        "quarantined_at": row.quarantined_at.isoformat() if row.quarantined_at else None,
    } for row in rows]


@router.post("/items/{item_key}/release")
async def release(item_key: str, body: ReleaseIn, current: dict = Depends(get_current_employer),
                  db: AsyncSession = Depends(get_db)):
    from app.services.staff import release_key

    employer = await _staff(current, db)
    row = await db.get(ItemStat, item_key)
    if row is None:
        raise ApiError(404, "not_found", "Задание не найдено")
    try:
        release_key(row, body.note.strip(), datetime.now(UTC))
    except ValueError as exc:
        if str(exc) == "identity":
            raise ApiError(422, "validation_error", "В заметке не должно быть имени, почты или телефона") from exc
        raise ApiError(409, "conflict", "Задание не в карантине") from exc
    db.add(MethodistLog(employer_id=employer.id, action="release", subject=item_key[:80],
                        note=body.note.strip(), created_at=datetime.now(UTC)))
    await db.commit()
    return {"item_key": row.item_key, "status": row.status}


@router.get("/log")
async def log(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    await _staff(current, db)
    rows = list(await db.scalars(select(MethodistLog).order_by(MethodistLog.created_at.desc()).limit(50)))
    return [{"id": str(row.id), "action": row.action, "subject": row.subject, "note": row.note,
             "created_at": row.created_at.isoformat()} for row in rows]
