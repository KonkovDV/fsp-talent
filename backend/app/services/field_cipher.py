"""AES-256-GCM for contact fields.

NIST SP 800-38D: a 96-bit nonce is never reused with the key, and the tag is 128 bits.
The associated data is the table, the column and the row, so a ciphertext cannot be
moved onto another person. Login does not search the ciphertext: it uses a separate HMAC.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import settings

PREFIX = "enc:v1:"
_SALT = b"fsp-talent-field-v1"


class FieldCipherError(ValueError):
    """The ciphertext does not open. The API must not show the stored bytes."""


def _ikm() -> bytes:
    raw = (settings.FIELD_ENCRYPTION_KEY or settings.SECRET_KEY).encode()
    return raw


def _derive(info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=_SALT, info=info).derive(_ikm())


def seal(owner: str, table: str, column: str, plain: str) -> str:
    """Encrypt one contact. Two calls on the same text do not share a nonce."""
    nonce = os.urandom(12)
    aad = f"{table}.{column}:{owner}".encode()
    body = AESGCM(_derive(b"aes-gcm")).encrypt(nonce, plain.encode("utf-8"), aad)
    return PREFIX + base64.b64encode(nonce + body).decode("ascii")


def open_seal(owner: str, table: str, column: str, stored: str) -> str:
    if not stored.startswith(PREFIX):
        return stored
    try:
        raw = base64.b64decode(stored[len(PREFIX):], validate=True)
        nonce, body = raw[:12], raw[12:]
        aad = f"{table}.{column}:{owner}".encode()
        return AESGCM(_derive(b"aes-gcm")).decrypt(nonce, body, aad).decode("utf-8")
    except (InvalidTag, ValueError, UnicodeDecodeError) as exc:
        raise FieldCipherError("Контакт не открывается") from exc


def blind_index(email: str) -> str:
    """Stable lookup key. It is not the address and not the ciphertext."""
    mac = hmac.new(_derive(b"email-bindex"), email.strip().lower().encode(), hashlib.sha256)
    return mac.hexdigest()


def email_is(model: Any, email: str):
    return model.email_bindex == blind_index(email)


_FIELDS = {
    "Participant": ("participants", ("email", "phone", "telegram", "guardian_email")),
    "Employer": ("employers", ("email",)),
    "Offer": ("offers", ("contact_method",)),
    "EmailVerification": ("email_verifications", ("email",)),
}


def _owner(obj: Any) -> str:
    if obj.id is None:
        obj.id = uuid.uuid4()
    return str(obj.id)


def _seal_obj(obj: Any) -> None:
    spec = _FIELDS.get(type(obj).__name__)
    if spec is None:
        return
    table, fields = spec
    owner = _owner(obj)
    restore: dict[str, str] = {}
    state = inspect(obj)
    for name in fields:
        value = getattr(obj, name)
        if value is None or value == "":
            if name == "email" and state.attrs.email.history.has_changes() and hasattr(obj, "email_bindex"):
                obj.email_bindex = None
            continue
        if isinstance(value, str) and value.startswith(PREFIX):
            continue
        restore[name] = value
        setattr(obj, name, seal(owner, table, name, value))
        if name == "email" and hasattr(obj, "email_bindex"):
            obj.email_bindex = blind_index(value)
    if restore:
        obj.__dict__["_seal_restore"] = restore


def _restore_obj(obj: Any) -> None:
    held = obj.__dict__.pop("_seal_restore", None)
    if not held:
        return
    for name, value in held.items():
        set_committed_value(obj, name, value)


def _open_obj(target: Any) -> None:
    spec = _FIELDS.get(type(target).__name__)
    if spec is None:
        return
    table, fields = spec
    owner = str(target.id)
    for name in fields:
        raw = getattr(target, name)
        if not isinstance(raw, str) or not raw.startswith(PREFIX):
            continue
        try:
            plain = open_seal(owner, table, name, raw)
        except FieldCipherError:
            plain = None
        set_committed_value(target, name, plain)


def install() -> None:
    """Seal contacts on the way to the database and open them on the way back."""
    if getattr(install, "_done", False):
        return
    install._done = True  # type: ignore[attr-defined]

    @event.listens_for(Session, "before_flush")
    def _before(session, flush_context, instances):  # noqa: ARG001
        for obj in list(session.new) + list(session.dirty):
            _seal_obj(obj)

    @event.listens_for(Session, "after_flush")
    def _after(session, flush_context):  # noqa: ARG001
        for obj in list(session.new) + list(session.dirty):
            _restore_obj(obj)

    from app.models.employer import Employer
    from app.models.identity import EmailVerification
    from app.models.offer import Offer
    from app.models.participant import Participant

    for model in (Participant, Employer, Offer, EmailVerification):
        event.listen(model, "load", lambda target, context: _open_obj(target))
