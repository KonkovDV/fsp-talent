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
import posixpath
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urlsplit

import httpx
from sqlalchemy import select, text

from app.services.ai.providers import ProviderError, _public_only
from app.services.field_cipher import open_seal, seal

DELAYS = (60, 300, 1800, 7200, 43200)
SKEW_SECONDS = 300
_OWN_PATH = "/api/v1/integrations/sandbox/"
# Events whose payload may still carry contacts after the person closed them.
_CONTACT_PAYLOAD_EVENTS = frozenset({"offer.accepted", "contacts.updated"})
_CONTACT_CHANNELS = ("email", "telegram", "phone", "github")


def without_closed_channels(body: dict, allowed: list[str]) -> dict | None:
    """Drop contact values the candidate has since closed. None means the payload is already inside the set.

    A retry of `offer.accepted` must not put a channel back after `contacts.updated` asked the ATS to delete it.
    """
    candidate = body.get("candidate")
    if not isinstance(candidate, dict):
        return None
    open_channels = set(allowed)
    shared = candidate.get("shared")
    leaked = [ch for ch in _CONTACT_CHANNELS if candidate.get(ch) and ch not in open_channels]
    shared_extra = [ch for ch in shared if ch not in open_channels] if isinstance(shared, list) else []
    if not leaked and not shared_extra:
        return None
    cleaned = dict(candidate)
    for ch in _CONTACT_CHANNELS:
        if ch not in open_channels:
            cleaned[ch] = None
    if isinstance(shared, list):
        cleaned["shared"] = [ch for ch in _CONTACT_CHANNELS if ch in shared and ch in open_channels]
    removed = [ch for ch in (candidate.get("removed") or []) if isinstance(ch, str)]
    for ch in leaked + shared_extra:
        if ch not in removed:
            removed.append(ch)
    cleaned["removed"] = removed
    return {**body, "candidate": cleaned}


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


async def first_delivery(endpoint_id: str, msg_id: str, skew: int = SKEW_SECONDS) -> bool:
    """SEC4: a signed message is accepted once. The webhook-id is remembered for the whole skew window
    (both sides of it), so a captured request cannot be replayed while its timestamp is still fresh.
    Redis down: refuse. A missed replay guard must not become an open door."""
    import logging

    from app.core.redis_client import get_redis

    try:
        redis = await get_redis()
        fresh = await redis.set(f"webhook:seen:{endpoint_id}:{msg_id[:128]}", "1", nx=True, ex=2 * skew)
        return bool(fresh)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).warning("webhook replay guard unavailable", exc_info=True)
        return False


def check_url(url: str) -> str:
    """https to a public host, or the stand's own sandbox receiver. Raises ValueError."""
    from app.core.config import settings

    parts = urlsplit(url.strip())
    if parts.username or parts.password or not parts.hostname:
        raise ValueError("некорректный адрес")
    base = urlsplit(settings.PUBLIC_BASE_URL)
    if parts.scheme == base.scheme and parts.hostname == base.hostname:
        # SEC3-02: the own-host exception is the sandbox receiver only: same port, and a path that stays
        # under it after decoding and normalisation (httpx collapses «../», so «/sandbox/../../metrics» is /metrics).
        if _port(parts) != _port(base) or not _own_path(parts.path):
            raise ValueError("на адрес стенда — только приёмник песочницы")
        return url.strip()
    if parts.scheme != "https":
        raise ValueError("снаружи принимается только https")
    try:
        _public_only(parts.hostname)
    except ProviderError as exc:
        raise ValueError(str(exc)) from exc
    return url.strip()


_DEFAULT_PORTS = {"http": 80, "https": 443}


def _port(parts) -> int | None:
    try:
        return parts.port or _DEFAULT_PORTS.get(parts.scheme)
    except ValueError:
        return None


def _own_path(path: str) -> bool:
    raw = unquote(unquote(path))
    if "\\" in raw or any(seg in ("..", ".") for seg in raw.split("/")):
        return False
    return posixpath.normpath(raw).startswith(_OWN_PATH.rstrip("/")) and raw.startswith(_OWN_PATH)


def _is_own(url: str) -> bool:
    from app.core.config import settings

    parts, base = urlsplit(url), urlsplit(settings.PUBLIC_BASE_URL)
    return parts.scheme == base.scheme and parts.hostname == base.hostname


def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(24)


def _store_secret(employer_id: uuid.UUID, plain: str) -> str:
    return seal(str(employer_id), "webhook_endpoints", "secret", plain)


def _read_secret(employer_id: uuid.UUID, stored: str) -> str:
    return open_seal(str(employer_id), "webhook_endpoints", "secret", stored)


_BYPASS = text("SELECT set_config('app.bypass_rls', :value, true)")


@asynccontextmanager
async def _company_rows(db):
    """Row-level security bypass for the statements inside, in the caller's transaction, then the old setting."""
    previous = await db.scalar(text("SELECT current_setting('app.bypass_rls', true)"))
    await db.execute(_BYPASS.bindparams(value="on"))
    try:
        yield
    finally:
        await db.execute(_BYPASS.bindparams(value=previous or ""))


async def drop_stale_contact_deliveries(db, employer_id: uuid.UUID, candidate_ref: str) -> int:
    """Mark pending offer.accepted / contacts.updated for this person as dead before contacts.revoked.

    Retries can otherwise deliver contacts after the revoke event already asked the ATS to delete them.
    """
    from app.models.webhook import WebhookDelivery, WebhookEndpoint

    if not candidate_ref:
        return 0
    await db.flush()
    dropped = 0
    async with _company_rows(db):
        rows = list(await db.scalars(
            select(WebhookDelivery)
            .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
            .where(WebhookEndpoint.employer_id == employer_id,
                   WebhookDelivery.status == "pending",
                   WebhookDelivery.event_type.in_(_CONTACT_PAYLOAD_EVENTS))))
        for row in rows:
            try:
                body = json.loads(row.payload)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            candidate = body.get("candidate") if isinstance(body, dict) else None
            if isinstance(candidate, dict) and candidate.get("ref") == candidate_ref:
                row.status, row.last_error = "dead", "superseded"
                dropped += 1
        if dropped:
            await db.flush()
    return dropped


async def enqueue(db, employer_id: uuid.UUID, event_type: str, payload: dict) -> int:
    """Write one delivery per active endpoint in the caller's transaction. Returns how many.

    The caller is often the candidate (accept, decline, closed contacts, erasure), and row-level security hides
    the company's endpoints from that scope. The request's own changes are flushed first under its own scope;
    only the endpoint lookup and the delivery rows run with the bypass. The delivery still commits or rolls
    back together with the change that caused it.
    """
    from app.models.webhook import WebhookDelivery, WebhookEndpoint

    await db.flush()
    async with _company_rows(db):
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
        if endpoints:
            await db.flush()
    return len(endpoints)


async def post_delivery(url: str, secret: str, delivery_id: str, payload: str) -> tuple[int, str]:
    body = payload.encode()
    headers = sign_headers(secret, delivery_id, body, datetime.now(UTC))
    transport = None
    if not _is_own(url):
        # SEC3-03: resolve once and connect to that checked address (DNS rebinding between check and send).
        from app.services.page_draft import PageDraftError, _Pinned, public_ip

        host = urlsplit(url).hostname or ""
        try:
            transport = _Pinned(host, public_ip(host))
        except PageDraftError as exc:
            raise ValueError(f"адрес не публичный: {exc}") from exc
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0), trust_env=False, follow_redirects=False,
                                     transport=transport) as client:
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
             .order_by(WebhookDelivery.next_at).limit(limit)
             # RT-07: two workers (or beat + the employer's "send now") must not POST the same row twice.
             .with_for_update(skip_locked=True, of=WebhookDelivery))
    if employer_id is not None:
        query = query.join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id).where(
            WebhookEndpoint.employer_id == employer_id)
    from app.models import Offer

    rows = list(await db.scalars(query))
    for row in rows:
        endpoint = await db.get(WebhookEndpoint, row.endpoint_id)
        if endpoint is None or not endpoint.active:
            row.status, row.last_error = "dead", "endpoint off"
            continue
        if row.event_type in _CONTACT_PAYLOAD_EVENTS:
            try:
                body = json.loads(row.payload)
            except (TypeError, ValueError, json.JSONDecodeError):
                body = None
            offer_id = ((body or {}).get("offer") or {}).get("id") if isinstance(body, dict) else None
            if offer_id:
                try:
                    offer = await db.get(Offer, uuid.UUID(str(offer_id)))
                except (TypeError, ValueError):
                    offer = None
                if offer is None or offer.contacts_revoked_at is not None:
                    row.status, row.last_error = "dead", "superseded"
                    continue
                from app.services.contact_scope import scope
                rewritten = without_closed_channels(body, scope(offer))
                if rewritten is not None:
                    row.payload = json.dumps(rewritten, ensure_ascii=False, separators=(",", ":"))
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
