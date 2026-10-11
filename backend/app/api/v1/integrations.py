"""ATS endpoints for one company, and the stand's own receiver.

The receiver is public: it trusts the signature, not a session. Reading an endpoint
from it needs the row-level bypass, because the caller is not signed in.
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.core.config import settings
from app.core.database import get_db
from app.core.rls import bypass_rls, reset_rls
from app.models import Offer, Participant, WebhookDelivery, WebhookEndpoint
from app.services.csv_safe import safe_row
from app.services.privacy import contacts_allowed
from app.services.webhooks import (
    _read_secret,
    _store_secret,
    check_url,
    deliver_due,
    enqueue,
    new_secret,
    first_delivery,
    signature_ok,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/employer/integrations", tags=["integrations"])
sandbox = APIRouter(prefix="/integrations", tags=["integrations"])
_MAX = 3


class EndpointIn(BaseModel):
    url: str | None = Field(None, max_length=500)
    use_sandbox: bool = False


def _eid(current: dict) -> uuid.UUID:
    return uuid.UUID(current["sub"])


@router.get("")
async def list_endpoints(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.employer_id == _eid(current))
                                 .order_by(WebhookEndpoint.created_at)))
    return [{"id": str(row.id), "url": row.url, "active": row.active,
             "created_at": row.created_at.isoformat()} for row in rows]


@router.post("", status_code=201)
async def create_endpoint(body: EndpointIn, current: dict = Depends(get_current_employer),
                          db: AsyncSession = Depends(get_db)):
    employer_id = _eid(current)
    count = len(list(await db.scalars(select(WebhookEndpoint.id).where(WebhookEndpoint.employer_id == employer_id))))
    if count >= _MAX:
        raise ApiError(409, "conflict", f"Адресов уже {_MAX}: удалите лишний")
    endpoint_id = uuid.uuid4()
    if body.use_sandbox:
        url = f"{settings.PUBLIC_BASE_URL}/api/v1/integrations/sandbox/{endpoint_id}"
    elif body.url:
        url = body.url.strip()
    else:
        raise ApiError(422, "validation_error", "Укажите адрес или приёмник стенда")
    try:
        url = check_url(url)
    except ValueError as exc:
        raise ApiError(422, "validation_error", str(exc)) from exc
    plain = new_secret()
    db.add(WebhookEndpoint(id=endpoint_id, employer_id=employer_id, url=url,
                           secret=_store_secret(employer_id, plain), created_at=datetime.now(UTC)))
    await db.commit()
    return {"id": str(endpoint_id), "url": url, "secret": plain}


@router.post("/{endpoint_id}/rotate")
async def rotate(endpoint_id: uuid.UUID, current: dict = Depends(get_current_employer),
                 db: AsyncSession = Depends(get_db)):
    row = await db.get(WebhookEndpoint, endpoint_id)
    if row is None or row.employer_id != _eid(current):
        raise ApiError(404, "not_found")
    plain = new_secret()
    row.secret = _store_secret(row.employer_id, plain)
    await db.commit()
    return {"id": str(row.id), "secret": plain}


@router.delete("/{endpoint_id}")
async def remove(endpoint_id: uuid.UUID, current: dict = Depends(get_current_employer),
                 db: AsyncSession = Depends(get_db)):
    row = await db.get(WebhookEndpoint, endpoint_id)
    if row is not None and row.employer_id == _eid(current):
        await db.delete(row)
        await db.commit()
    return {"removed": row is not None}


@router.get("/deliveries")
async def deliveries(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
        .where(WebhookEndpoint.employer_id == _eid(current))
        .order_by(WebhookDelivery.created_at.desc()).limit(50)))
    return [{
        "id": str(row.id), "event_type": row.event_type, "status": row.status, "attempt": row.attempt,
        "last_code": row.last_code, "last_error": row.last_error, "created_at": row.created_at.isoformat(),
    } for row in rows]


@router.post("/test")
async def send_test(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """A sample with no person. Delivered immediately, then the worker retries what failed."""
    employer_id = _eid(current)
    queued = await enqueue(db, employer_id, "offer.accepted", {
        "created_at": datetime.now(UTC).isoformat(), "employer_id": str(employer_id), "demo": True,
        "offer": {"role": "Backend-разработчик", "salary_from": 180000, "salary_to": 240000, "work_format": "remote"},
        "candidate": {"ref": "demo", "category": {"specialization": "backend", "grade": "middle"}},
    })
    await db.commit()
    sent = 0
    if queued:
        try:
            sent = await deliver_due(db, employer_id)
            await db.commit()
        except Exception:
            logger.exception("test delivery failed")
            await db.rollback()
    return {"queued": queued, "attempted": sent}


@router.get("/export")
async def export(fmt: str = Query("json", pattern="^(json|csv)$"),
                 current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """People who agreed to contact and have not closed it. Declined invitations stay out."""
    employer_id = _eid(current)
    offers = list(await db.scalars(select(Offer).where(
        Offer.employer_id == employer_id, Offer.status == "accepted", Offer.contacts_revoked_at.is_(None))))
    rows = []
    for offer in offers:
        person = await db.get(Participant, offer.candidate_id)
        if person is None or not await contacts_allowed(db, person):
            continue
        rows.append({
            "ref": str(person.id), "name": person.display_name, "email": person.email,
            "phone": person.phone, "telegram": person.telegram, "source": "offer", "role": offer.role,
        })
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["ref", "name", "email", "phone", "telegram", "source", "role"])
        writer.writeheader()
        writer.writerows(safe_row(r) for r in rows)
        return Response(buf.getvalue(), media_type="text/csv")
    return {"items": rows}


@sandbox.post("/sandbox/{endpoint_id}", status_code=204)
async def receive(endpoint_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """The stand's receiver. A wrong signature is rejected; the body is not stored here."""
    body = await request.body()
    if len(body) > 65_536:
        raise ApiError(413, "payload_too_large")
    token = bypass_rls()
    try:
        row = await db.get(WebhookEndpoint, endpoint_id)
        if row is None or not row.active:
            raise ApiError(404, "not_found")
        secret = _read_secret(row.employer_id, row.secret)
        if not signature_ok(secret, request.headers, body, datetime.now(UTC)):
            raise ApiError(401, "invalid_credentials", "Подпись не сошлась")
        if not await first_delivery(str(endpoint_id), request.headers.get("webhook-id", "")):
            raise ApiError(409, "conflict", "Это сообщение уже принято (webhook-id)")
    finally:
        reset_rls(token)
    return Response(status_code=204)
