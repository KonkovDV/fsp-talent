"""The bell: hiring events for the signed-in candidate or employer."""
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_any_auth
from app.api.errors import ApiError
from app.core.database import get_db
from app.models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _me(current: dict) -> tuple[str, uuid.UUID]:
    role = current.get("role")
    if role not in ("participant", "employer"):
        raise ApiError(403, "forbidden")
    return role, uuid.UUID(current["sub"])


def _out(n: Notification) -> dict:
    return {"id": str(n.id), "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
            "created_at": n.created_at.isoformat(), "read": n.read_at is not None}


@router.get("")
async def list_notifications(limit: int = Query(15, ge=1, le=50), current: dict = Depends(get_any_auth),
                             db: AsyncSession = Depends(get_db)):
    role, me = _me(current)
    mine = (Notification.recipient_role == role, Notification.recipient_id == me)
    rows = await db.scalars(select(Notification).where(*mine).order_by(Notification.created_at.desc()).limit(limit))
    unread = await db.scalar(select(func.count()).select_from(Notification)
                             .where(*mine, Notification.read_at.is_(None)))
    return {"unread": unread or 0, "items": [_out(n) for n in rows]}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: uuid.UUID, current: dict = Depends(get_any_auth),
                    db: AsyncSession = Depends(get_db)):
    role, me = _me(current)
    n = await db.get(Notification, notification_id)
    if n is None or n.recipient_role != role or n.recipient_id != me:
        raise ApiError(404, "not_found")
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
        await db.commit()
    return _out(n)


@router.post("/read-all")
async def mark_all_read(current: dict = Depends(get_any_auth), db: AsyncSession = Depends(get_db)):
    role, me = _me(current)
    result = await db.execute(update(Notification).where(
        Notification.recipient_role == role, Notification.recipient_id == me, Notification.read_at.is_(None),
    ).values(read_at=datetime.now(UTC)))
    await db.commit()
    return {"marked": result.rowcount}
