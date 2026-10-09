"""Consent of a legal representative (part 6 of article 9 of 152-FZ) for a candidate aged 15 to 17.

Registration is open from 15. A minor names the guardian's email in the profile; the guardian receives a
signed link and confirms. The signature covers the participant and that exact email, so the link stops
working when the email changes. Until the guardian confirms, the card is not shown to employers.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import uuid

from app.core.config import settings

MIN_AGE = 15


def _mac(participant_id: uuid.UUID, email: str) -> str:
    msg = f"guardian:{participant_id}:{email.strip().lower()}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:40]


def guardian_token(participant_id: uuid.UUID, email: str) -> str:
    head = base64.urlsafe_b64encode(participant_id.bytes).decode().rstrip("=")
    return f"{head}.{_mac(participant_id, email)}"


def consent_link(base: str, token: str) -> str:
    """The token rides in the fragment, so the access log and the Referer never see it."""
    return f"{base.rstrip('/')}/guardian#token={token}"


def token_participant(token: str) -> uuid.UUID | None:
    """The participant id inside the token, before the signature is checked against the stored email."""
    head, _, _ = (token or "").partition(".")
    try:
        return uuid.UUID(bytes=base64.urlsafe_b64decode(head + "=" * (-len(head) % 4)))
    except (ValueError, TypeError):
        return None


def token_valid(token: str, participant_id: uuid.UUID, email: str | None) -> bool:
    if not email:
        return False
    _, _, mac = (token or "").partition(".")
    return hmac.compare_digest(mac, _mac(participant_id, email))
