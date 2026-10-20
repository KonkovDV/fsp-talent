"""W3C Bitstring Status List v1.0 (W3C Recommendation, 15 May 2025) for revocation.

Every credential with a status gets a random position in one public list. The list is a bitstring of
131 072 entries (the minimum the specification asks for, so one position does not single a person out),
GZIP-compressed and published as a signed credential. A set bit means "revoked". The bit is read from
`verifiable_credentials.revoked_at` when the list is served, so a revocation needs no second write.

The first position is the left-most bit of the first byte. `encodedList` is multibase base64url without
padding (prefix "u"). https://www.w3.org/TR/vc-bitstring-status-list/
"""
from __future__ import annotations

import base64
import gzip
import logging
import secrets
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

LIST_ID = 1
LIST_SIZE = 131_072
PURPOSE = "revocation"
_TRIES = 64
logger = logging.getLogger(__name__)


def list_url(list_id: int = LIST_ID) -> str:
    return f"{settings.PUBLIC_BASE_URL}/api/v1/public/status-lists/{list_id}"


def status_entry(index: int, list_id: int = LIST_ID) -> dict:
    if not 0 <= index < LIST_SIZE:
        raise ValueError("index")
    return {
        "id": f"{list_url(list_id)}#{index}",
        "type": "BitstringStatusListEntry",
        "statusPurpose": PURPOSE,
        "statusListIndex": str(index),
        "statusListCredential": list_url(list_id),
    }


def encode(indices: Iterable[int], size: int = LIST_SIZE) -> str:
    bits = bytearray(size // 8)
    for index in indices:
        if 0 <= index < size:
            bits[index // 8] |= 0x80 >> (index % 8)
    packed = gzip.compress(bytes(bits), mtime=0)
    return "u" + base64.urlsafe_b64encode(packed).decode().rstrip("=")


def decode(encoded: str) -> bytes:
    if not encoded.startswith("u"):
        raise ValueError("multibase")
    body = encoded[1:]
    return gzip.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


def is_set(raw: bytes, index: int) -> bool:
    if not 0 <= index < len(raw) * 8:
        raise ValueError("index")
    return bool(raw[index // 8] & (0x80 >> (index % 8)))


async def allocate_index(db: AsyncSession, taken: set[int] | None = None) -> int | None:
    """A free random position, or None when 64 random tries found none.

    None means the list is nearly full: the credential is issued with its own status only, issuance does
    not fail. The unique constraint uq_vc_status_index still guards a race between two requests.
    """
    from app.models.vc import VerifiableCredential

    taken = taken if taken is not None else set()
    for _ in range(_TRIES):
        index = secrets.randbelow(LIST_SIZE)
        if index in taken:
            continue
        used = await db.scalar(select(VerifiableCredential.id).where(VerifiableCredential.status_index == index))
        if used is None:
            taken.add(index)
            return index
    logger.warning("status list %s has no free position: credential issued without a list entry", LIST_ID)
    return None


def list_credential(revoked: Iterable[int], list_id: int = LIST_ID) -> dict:
    """The signed status list. A verifier fetches it once and checks any number of credentials offline."""
    from app.services.vc.issuer import _now, issuer_id, sign_document

    url = list_url(list_id)
    now = _now()
    document = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": url,
        "type": ["VerifiableCredential", "BitstringStatusListCredential"],
        "issuer": issuer_id(),
        "validFrom": now,
        "credentialSubject": {
            "id": f"{url}#list",
            "type": "BitstringStatusList",
            "statusPurpose": PURPOSE,
            "encodedList": encode(revoked),
        },
    }
    return sign_document(document, now)
