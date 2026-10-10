"""Hiring events to the company's ATS.

Signing follows Standard Webhooks: webhook-id, webhook-timestamp and
webhook-signature v1 over "{id}.{timestamp}.{body}". The older
X-FSP-Talent-Signature header is sent as well.

A receiver that answers 410 is not retried. Other failures wait 1 min, 5 min,
30 min, 2 h and 12 h, then the delivery is dead. Redirects are not followed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from app.services.ai.providers import ProviderError, _public_only
from app.services.field_cipher import open_seal, seal

DELAYS = (60, 300, 1800, 7200, 43200)
SKEW_SECONDS = 300
_OWN_PATH = "/api/v1/integrations/sandbox/"


def classify(code: int, attempt: int) -> tuple[str, int | None]:
    """Next status and how many seconds to wait. No wait means the series stops."""
    if code in (200, 201, 202, 204):
        return "delivered", None
    if code == 410:
        return "dead", None
    if attempt >= len(DELAYS):
        return "dead", None
    return "pending", DELAYS[attempt]


def sign_headers(secret: str, delivery_id: str, body: bytes, now: datetime) -> dict[str, str]:
    stamp = str(int(now.timestamp()))
    signed = f"{delivery_id}.{stamp}.".encode() + body
    mac = base64.b64encode(hmac.new(secret.encode(), signed, hashlib.sha256).digest()).decode()
    legacy = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {
        "webhook-id": delivery_id,
        "webhook-timestamp": stamp,
        "webhook-signature": f"v1,{mac}",
        "X-FSP-Talent-Signature": legacy,
        "Content-Type": "application/json",
    }


def signature_ok(secret: str, headers, body: bytes, now: datetime, skew: int = SKEW_SECONDS) -> bool:
    msg_id = headers.get("webhook-id")
    stamp = headers.get("webhook-timestamp")
    offered = headers.get("webhook-signature") or ""
    if not msg_id or not stamp or not offered.startswith("v1,"):
        return False
    try:
        sent = int(stamp)
    except ValueError:
        return False
    if abs(now.timestamp() - sent) > skew:
        return False
    expected = base64.b64encode(
        hmac.new(secret.encode(), f"{msg_id}.{stamp}.".encode() + body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, offered.split(",", 1)[1].strip())


def check_url(url: str) -> str:
    """https to a public host, or the stand's own sandbox receiver. Raises ValueError."""
    from app.core.config import settings

    parts = urlsplit(url.strip())
    if parts.username or parts.password or not parts.hostname:
        raise ValueError("некорректный адрес")
    base = urlsplit(settings.PUBLIC_BASE_URL)
    own = (parts.scheme == base.scheme and parts.hostname == base.hostname
           and parts.path.startswith(_OWN_PATH))
    if own:
        return url.strip()
    if parts.scheme != "https":
        raise ValueError("снаружи принимается только https")
    try:
        _public_only(parts.hostname)
    except ProviderError as exc:
        raise ValueError(str(exc)) from exc
    return url.strip()


def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(24)


def _store_secret(employer_id: uuid.UUID, plain: str) -> str:
    return seal(str(employer_id), "webhook_endpoints", "secret", plain)


def _read_secret(employer_id: uuid.UUID, stored: str) -> str:
    return open_seal(str(employer_id), "webhook_endpoints", "secret", stored)


async def enqueue(db, employer_id: uuid.UUID, event_type: str, payload: dict) -> int:
    """Write one delivery per active endpoint in the caller's transaction. Returns how many."""
    from app.models.webhook import WebhookDelivery, WebhookEndpoint

    endpoints = list(await db.scalars(select(WebhookEndpoint).where(
        WebhookEndpoint.employer_id == employer_id, WebhookEndpoint.active.is_(True))))
    now = datetime.now(UTC)
    for endpoint in endpoints:
        delivery_id = uuid.uuid4()
        body = {**payload, "event_id": str(delivery_id), "type": event_type}
        db.add(WebhookDelivery(
            id=delivery_id, endpoint_id=endpoint.id, event_type=event_type,
            payload=json.dumps(body, ensure_ascii=False, separators=(",", ":")),
            attempt=0, status="pending", next_at=now, created_at=now))
    return len(endpoints)


async def post_delivery(url: str, secret: str, delivery_id: str, payload: str) -> tuple[int, str]:
    body = payload.encode()
    headers = sign_headers(secret, delivery_id, body, datetime.now(UTC))
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0), trust_env=False, follow_redirects=False) as client:
            response = await client.post(url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        return 0, type(exc).__name__
    if response.is_redirect:
        return response.status_code, "redirect"
    return response.status_code, ""


async def deliver_due(db, employer_id: uuid.UUID | None = None, limit: int = 20) -> int:
    """Send deliveries that are due. The caller commits."""
    from app.models.webhook import WebhookDelivery, WebhookEndpoint

    now = datetime.now(UTC)
    query = (select(WebhookDelivery)
             .where(WebhookDelivery.status == "pending", WebhookDelivery.next_at <= now)
             .order_by(WebhookDelivery.next_at).limit(limit))
    if employer_id is not None:
        query = query.join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id).where(
            WebhookEndpoint.employer_id == employer_id)
    rows = list(await db.scalars(query))
    for row in rows:
        endpoint = await db.get(WebhookEndpoint, row.endpoint_id)
        if endpoint is None or not endpoint.active:
            row.status, row.last_error = "dead", "endpoint off"
            continue
        try:
            secret = _read_secret(endpoint.employer_id, endpoint.secret)
            check_url(endpoint.url)
            code, error = await post_delivery(endpoint.url, secret, str(row.id), row.payload)
        except ValueError as exc:
            code, error = 0, str(exc)[:300]
        status, delay = classify(code, row.attempt)
        row.last_code, row.last_error, row.status = code or None, (error or None), status
        if delay is not None:
            row.attempt += 1
            row.next_at = now + timedelta(seconds=delay)
    return len(rows)
