"""Read-only API keys for a company's ATS.

The key is `fspk_<prefix>_<secret>`. Only its SHA-256 is stored, so a database dump does not
hand out working keys. The full key is returned once, at creation. A key reads the company's own
export and nothing else; it never signs in, never writes. Every new key has a term of at most a year:
a key forgotten in an old ATS config stops working by itself.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime

KEY_RE = re.compile(r"^fspk_([A-Za-z0-9]{8})_([A-Za-z0-9_-]{32,64})$")
MAX_ACTIVE = 3
TERM_DAYS = 90
MAX_TERM_DAYS = 365


def usable(row, now: datetime) -> bool:
    """Not revoked and not past its term. A key without a term predates terms and stays usable."""
    if getattr(row, "revoked_at", None) is not None:
        return False
    expires = getattr(row, "expires_at", None)
    return expires is None or expires > now


def new_key() -> tuple[str, str, str]:
    """(full key, prefix, hash). The prefix is shown in the list so the company can tell keys apart."""
    prefix = secrets.token_hex(4)
    full = f"fspk_{prefix}_{secrets.token_urlsafe(32)}"
    return full, prefix, key_hash(full)


def key_hash(full: str) -> str:
    return hashlib.sha256(full.encode("utf-8")).hexdigest()


def well_formed(full: str | None) -> bool:
    return bool(full) and KEY_RE.match(full) is not None


def same_hash(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
