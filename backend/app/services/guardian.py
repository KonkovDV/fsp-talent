"""Consent of a legal representative (part 6 of article 9 of 152-FZ) for a candidate aged 15 to 17.

Registration is open from 15. A minor names the guardian's email in the profile; the guardian receives a
signed link and confirms. The signature covers the participant and that exact email, so the link stops
working when the email changes. Until the guardian confirms, the card is not shown to employers.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid

from app.core.config import settings
from app.core.demo_guard import is_protected

MIN_AGE = 15
_GMAIL = frozenset({"gmail.com", "googlemail.com"})


def _mailbox_key(email: str) -> tuple[str, str] | None:
    """Local part and domain, with the person's own plus-alias and Gmail dots folded in."""
    local, sep, domain = email.strip().lower().partition("@")
    if not sep or not local or not domain or "@" in domain:
        return None
    local = local.split("+", 1)[0]
    if domain in _GMAIL:
        local = local.replace(".", "")
        domain = "gmail.com"
    return local, domain


def same_person_mailbox(left: str | None, right: str | None) -> bool:
    """True when both addresses are the same mailbox, including a plus-alias of the child."""
    if not left or not right:
        return False
    a, b = _mailbox_key(left), _mailbox_key(right)
    return a is not None and a == b


# A letter is not a standing authority. Seven days, then the minor asks again.
TOKEN_TTL_SECONDS = 7 * 24 * 3600


def _mac(participant_id: uuid.UUID, email: str, generation: int, issued_at: int) -> str:
    msg = f"guardian:{participant_id}:{email.strip().lower()}:{generation}:{issued_at}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:40]


def guardian_token(participant_id: uuid.UUID, email: str, generation: int = 0,
                   issued_at: int | None = None) -> str:
    issued = int(time.time()) if issued_at is None else int(issued_at)
    head = base64.urlsafe_b64encode(participant_id.bytes).decode().rstrip("=")
    return f"{head}.{int(generation)}.{issued}.{_mac(participant_id, email, int(generation), issued)}"


def consent_link(base: str, token: str) -> str:
    """The token rides in the fragment, so the access log and the Referer never see it."""
    return f"{base.rstrip('/')}/guardian#token={token}"


def demo_consent_link(participant_id: uuid.UUID, email: str | None, generation: int = 0) -> str | None:
    """The link on the participant's own screen, when the stand does not send letters.

    Both demo flags are required, the same rule as the registration code. A protected demo
    address does not get one: those accounts are shared, and the link would confirm consent.
    """
    if not email or not (settings.DEMO_MODE and settings.DEMO_SHOW_CODE):
        return None
    if is_protected(email):
        return None
    return consent_link(settings.PUBLIC_BASE_URL, guardian_token(participant_id, email, generation))


def token_participant(token: str) -> uuid.UUID | None:
    """The participant id inside the token, before the signature is checked against the stored email."""
    head, _, _ = (token or "").partition(".")
    try:
        return uuid.UUID(bytes=base64.urlsafe_b64decode(head + "=" * (-len(head) % 4)))
    except (ValueError, TypeError):
        return None


def token_parts(token: str) -> tuple[uuid.UUID, int, int, str] | None:
    pieces = (token or "").split(".")
    if len(pieces) != 4 or any(part == "" for part in pieces):
        return None
    head, generation, issued, mac = pieces
    try:
        participant_id = uuid.UUID(bytes=base64.urlsafe_b64decode(head + "=" * (-len(head) % 4)))
        return participant_id, int(generation), int(issued), mac
    except (ValueError, TypeError):
        return None


def token_valid(token: str, participant_id: uuid.UUID, email: str | None, generation: int = 0,
                now: int | None = None) -> bool:
    if not email:
        return False
    parts = token_parts(token)
    if parts is None or parts[0] != participant_id or parts[1] != int(generation):
        return False
    _, _, issued, mac = parts
    moment = int(time.time()) if now is None else int(now)
    if issued > moment + 120 or moment - issued > TOKEN_TTL_SECONDS:
        return False
    expected = _mac(participant_id, email, int(generation), issued)
    if len(mac) != len(expected):
        return False
    return hmac.compare_digest(mac, expected)
