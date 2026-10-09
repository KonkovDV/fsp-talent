"""A signed sample for the employer's ATS. The stand does not call an outside address.

The body is the same shape as the concept in TRUST_AND_ATS.md. Contacts stay out:
they leave the platform only after the candidate agrees, and this sample is not a person.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime


def sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def sample_event(employer_id: str) -> dict:
    return {
        "event_id": secrets.token_hex(8),
        "type": "offer.accepted",
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "employer_id": employer_id,
        "demo": True,
        "candidate": {
            "ref": "demo",
            "category": {"specialization": "backend", "grade": "middle", "grade_source": "assessed"},
        },
        "offer": {
            "role": "Backend-разработчик",
            "salary_from": 180_000,
            "salary_to": 240_000,
            "work_format": "remote",
        },
    }


def receipt(employer_id: str) -> dict:
    secret = secrets.token_hex(16)
    event = sample_event(employer_id)
    body = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode()
    signature = sign(secret, body)
    tampered = sign(secret, body + b" ")
    return {
        "event": event,
        "signature": signature,
        "valid": hmac.compare_digest(signature, sign(secret, body)),
        "tamper_rejected": not hmac.compare_digest(signature, tampered),
        "delivered": False,
    }
