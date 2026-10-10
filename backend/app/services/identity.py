"""Email confirmation, password reset and consents for both roles."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.core.config import settings
from app.core.ratelimit import RateLimitUnavailable, too_many
from app.legal import get_document, required_kinds
from app.models import Consent, ConsentLog, EmailVerification
from app.services.mail import send_mail

MAX_CODE_ATTEMPTS = 5
ROLE_LABEL = {"participant": "кандидата", "employer": "работодателя"}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _digest(value: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def visitor_ip(request) -> str:
    """Client address. The proxy header counts only when the socket peer is the proxy itself."""
    import ipaddress

    peer = request.client.host if request.client is not None and request.client.host else ""
    recorded = (request.headers.get("x-real-ip") or "").strip()
    try:
        address = ipaddress.ip_address(peer) if peer else None
    except ValueError:
        address = None
    if recorded and address is not None and not address.is_global:
        return recorded[:64]
    return peer or "unknown"


def client_fingerprint(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    ip = visitor_ip(request)
    ua = (request.headers.get("user-agent") or "")[:300] or None
    return (_digest(f"ip:{ip}") if ip else None), ua


async def issue_code(db: AsyncSession, subject_type: str, subject_id: uuid.UUID, email: str,
                     purpose: str) -> tuple[str, str]:
    """New 6-digit code and link token; earlier unused ones for the same purpose stop working."""
    now = datetime.now(UTC)
    await db.execute(
        update(EmailVerification)
        .where(EmailVerification.subject_type == subject_type, EmailVerification.subject_id == subject_id,
               EmailVerification.purpose == purpose, EmailVerification.consumed_at.is_(None))
        .values(consumed_at=now))
    code = f"{secrets.randbelow(1_000_000):06d}"
    token = secrets.token_urlsafe(32)
    db.add(EmailVerification(
        subject_type=subject_type, subject_id=subject_id, purpose=purpose, email=email,
        code_hash=_digest(f"code:{email}:{code}"), token_hash=_digest(f"token:{token}"),
        expires_at=now + timedelta(minutes=settings.EMAIL_CODE_TTL_MINUTES),
    ))
    await db.flush()
    return code, token


def letter(role: str, purpose: str, code: str, token: str) -> tuple[str, str]:
    """The code stays in the body. The link keeps its token in the fragment, not the query."""
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    ttl = settings.EMAIL_CODE_TTL_MINUTES
    if purpose == "verify":
        subject = "Код подтверждения FSP Talent"
        text = (f"Вы регистрируете аккаунт {ROLE_LABEL[role]} на FSP Talent.\n\n"
                f"Код подтверждения: {code}\n"
                f"Или откройте ссылку: {base}/verify#token={token}\n\n"
                f"Код действует {ttl} минут. Если вы не регистрировались, просто удалите письмо.")
    else:
        subject = "Сброс пароля FSP Talent"
        text = (f"Код для сброса пароля: {code}\n"
                f"Код действует {ttl} минут. Если вы не запрашивали сброс, ничего делать не нужно.")
    return subject, text


async def send_already_registered(email: str, role: str) -> None:
    """Tell the mailbox the address is taken. The HTTP answer stays the same as a new registration."""
    who = "кандидата" if role == "participant" else "работодателя"
    await send_mail(
        email,
        "Аккаунт уже есть",
        f"На этот адрес уже зарегистрирован аккаунт {who}. Войдите или восстановите пароль. "
        "Новый пароль не записан.",
    )


async def send_code(email: str, role: str, purpose: str, code: str, token: str) -> None:
    subject, text = letter(role, purpose, code, token)
    await send_mail(email, subject, text, meta={"purpose": purpose, "role": role, "code": code, "token": token})


async def check_resend_allowed(email: str, purpose: str) -> None:
    try:
        per_minute = await too_many(f"mail:{purpose}:min:{email}", limit=1, window_seconds=60, fail_closed=True)
        per_day = await too_many(f"mail:{purpose}:day:{email}", limit=8, window_seconds=86400, fail_closed=True)
    except RateLimitUnavailable:
        raise ApiError(503, "unavailable", "Отправка писем временно недоступна. Повторите через минуту.") from None
    if per_minute:
        raise ApiError(429, "resend_cooldown", headers={"Retry-After": "60"})
    if per_day:
        raise ApiError(429, "rate_limited", "Лимит писем на сегодня исчерпан")


async def consume_code(db: AsyncSession, email: str, code: str, purpose: str,
                       subject_type: str | None = None) -> EmailVerification:
    from app.services.field_cipher import email_is
    now = datetime.now(UTC)
    query = select(EmailVerification).where(
        email_is(EmailVerification, email), EmailVerification.purpose == purpose,
        EmailVerification.consumed_at.is_(None)).with_for_update()
    if subject_type:
        query = query.where(EmailVerification.subject_type == subject_type)
    rows = list(await db.scalars(query.order_by(EmailVerification.created_at.desc())))
    if not rows:
        raise ApiError(400, "verification_invalid")
    wanted = _digest(f"code:{email}:{code.strip()}")
    for row in rows:
        if hmac.compare_digest(row.code_hash, wanted):
            if row.expires_at <= now:
                raise ApiError(400, "verification_expired")
            if row.attempts >= MAX_CODE_ATTEMPTS:
                raise ApiError(400, "verification_attempts")
            row.consumed_at = now
            return row
    for row in rows:
        row.attempts += 1
    await db.commit()
    if any(row.attempts >= MAX_CODE_ATTEMPTS for row in rows):
        raise ApiError(400, "verification_attempts")
    raise ApiError(400, "verification_invalid")


async def consume_token(db: AsyncSession, token: str) -> EmailVerification:
    row = await db.scalar(select(EmailVerification).where(
        EmailVerification.token_hash == _digest(f"token:{token.strip()}"),
        EmailVerification.purpose == "verify").with_for_update())
    if row is None or row.consumed_at is not None:
        raise ApiError(400, "verification_invalid")
    if row.expires_at <= datetime.now(UTC):
        raise ApiError(400, "verification_expired")
    row.consumed_at = datetime.now(UTC)
    return row


# ── consents ────────────────────────────────────────────────────────────────

def check_required_consents(role: str, accepted: list[str]) -> None:
    missing = [k for k in required_kinds(role) if k not in set(accepted)]
    if missing:
        raise ApiError(422, "consent_required", details={"missing": missing})
    unknown = [k for k in accepted if get_document(k) is None or role not in get_document(k).roles]
    if unknown:
        raise ApiError(422, "consent_unknown", details={"unknown": unknown})


async def active_consent(db: AsyncSession, subject_type: str, subject_id: uuid.UUID, kind: str) -> Consent | None:
    return await db.scalar(select(Consent).where(
        Consent.subject_type == subject_type, Consent.subject_id == subject_id, Consent.kind == kind,
        Consent.withdrawn_at.is_(None)))


async def give_consent(db: AsyncSession, subject_type: str, subject_id: uuid.UUID, kind: str,
                       request: Request | None = None) -> Consent:
    doc = get_document(kind)
    if doc is None or subject_type not in doc.roles:
        raise ApiError(404, "consent_unknown")
    current = await active_consent(db, subject_type, subject_id, kind)
    if current is not None and current.version == doc.version and current.sha256 == doc.sha256:
        return current
    now = datetime.now(UTC)
    if current is not None:
        current.withdrawn_at = now   # superseded by the new version
        await db.flush()
    ip_hash, ua = client_fingerprint(request)
    consent = Consent(subject_type=subject_type, subject_id=subject_id, kind=kind, version=doc.version,
                      sha256=doc.sha256, given_at=now, ip_hash=ip_hash, user_agent=ua)
    db.add(consent)
    if subject_type == "participant":
        db.add(ConsentLog(participant_id=subject_id, event_type=f"consent_given:{kind}", actor_id=subject_id,
                          ip_hash=ip_hash, meta={"kind": kind, "version": doc.version, "sha256": doc.sha256}))
    await db.flush()
    return consent


async def withdraw_consent(db: AsyncSession, subject_type: str, subject_id: uuid.UUID, kind: str,
                           request: Request | None = None) -> Consent | None:
    current = await active_consent(db, subject_type, subject_id, kind)
    if current is None:
        return None
    current.withdrawn_at = datetime.now(UTC)
    if subject_type == "participant":
        ip_hash, _ = client_fingerprint(request)
        db.add(ConsentLog(participant_id=subject_id, event_type=f"consent_withdrawn:{kind}", actor_id=subject_id,
                          ip_hash=ip_hash, meta={"kind": kind, "version": current.version}))
    await db.flush()
    return current
