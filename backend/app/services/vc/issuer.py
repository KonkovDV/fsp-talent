"""
Verifiable Credentials: W3C VC Data Model 2.0 secured with Data Integrity `eddsa-jcs-2022`.

The issuer is the platform itself: it attests that the achievement was received from the
FSP system. Once FSP signs credentials with its own key, only the issuer block changes.

Canonicalization: sorted keys, compact separators, UTF-8. This matches RFC 8785 (JCS) for
credentials without floats and astral-plane keys, which holds for everything issued here.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
from datetime import UTC, datetime
from functools import lru_cache

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.core.config import settings

logger = logging.getLogger(__name__)
CRYPTOSUITE = "eddsa-jcs-2022"
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_ED25519_PUB_MULTICODEC = b"\xed\x01"


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\x00"))) + out


def _b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + _B58.index(ch)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * (len(s) - len(s.lstrip("1"))) + body


def _jcs(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@lru_cache(maxsize=1)
def _private_key() -> Ed25519PrivateKey:
    path = settings.VC_PRIVATE_KEY_PATH
    if os.path.exists(path):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        logger.warning(f"Generated new VC signing key at {path}")
    except FileExistsError:
        _private_key.cache_clear()
        return _private_key()
    except OSError:
        logger.error(f"Cannot persist VC key to {path}; credentials will not survive restart")
    return key


def issuer_id() -> str:
    return f"{settings.PUBLIC_BASE_URL}/api/v1/public/issuer"


@lru_cache(maxsize=1)
def public_key_multibase() -> str:
    raw = _private_key().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return "z" + _b58encode(_ED25519_PUB_MULTICODEC + raw)


@lru_cache(maxsize=1)
def _public_key_obj() -> Ed25519PublicKey:
    raw = _b58decode(public_key_multibase()[1:])[len(_ED25519_PUB_MULTICODEC):]
    return Ed25519PublicKey.from_public_bytes(raw)


def issuer_document() -> dict:
    return {
        "id": issuer_id(),
        "name": "ФСП Талант (прототип платформы)",
        "verificationMethod": [{
            "id": f"{issuer_id()}#key-1",
            "type": "Multikey",
            "controller": issuer_id(),
            "publicKeyMultibase": public_key_multibase(),
        }],
    }


def _open_badge(achievement: dict) -> dict:
    """Open Badges 3 achievement: a name, criteria, and type Achievement. Extra claims stay."""
    achievement = dict(achievement)
    kind = achievement.get("type")
    if kind == "Achievement" or kind is None:
        achievement["type"] = ["Achievement"]
    elif isinstance(kind, str):
        achievement["type"] = ["Achievement", kind]
    achievement.setdefault("name", achievement.get("eventName") or "Результат ФСП")
    achievement.setdefault("criteria", {"narrative": "Строка протокола, полученная платформой от реестра ФСП."})
    return achievement


def issue_derived_credential(credential_id: str, subject_id: str, *, year: int, status: str,
                             bucket: str, discipline: str) -> dict:
    """A signed card with the year, the competition status and the place band.

    The event title and the holder's name are not in the document. It is not stored, so it has no
    revocation entry: the signature is the whole check.
    """
    return issue_achievement_credential(credential_id, subject_id, {
        "type": "DerivedFSPClaim",
        "name": f"Результат ФСП, {year}",
        "year": year,
        "competitionStatus": status,
        "bucket": bucket,
        "discipline": discipline,
        "criteria": {"narrative": "Год, статус соревнования и корзина места. Название события и имя не входят."},
    }, status=False)


def _hash_data(document: dict, proof_config: dict) -> bytes:
    return hashlib.sha256(_jcs(proof_config)).digest() + hashlib.sha256(_jcs(document)).digest()


def issue_achievement_credential(credential_id: str, subject_id: str, achievement: dict, *,
                                  status: bool = True) -> dict:
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    achievement = _open_badge(achievement)
    document = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
        ],
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "id": f"urn:uuid:{credential_id}",
        "issuer": {"id": issuer_id(), "name": "ФСП Талант (прототип платформы)"},
        "validFrom": now,
        "credentialSubject": {
            "id": f"urn:uuid:{subject_id}",
            "type": ["AchievementSubject"],
            "achievement": achievement,
        },
    }
    if status:
        document["credentialStatus"] = {
            "id": f"{settings.PUBLIC_BASE_URL}/api/v1/public/credentials/{credential_id}/status",
            "type": "FSPCredentialStatus",
        }
    proof_config = {
        "@context": document["@context"],
        "type": "DataIntegrityProof",
        "cryptosuite": CRYPTOSUITE,
        "created": now,
        "verificationMethod": f"{issuer_id()}#key-1",
        "proofPurpose": "assertionMethod",
    }
    signature = _private_key().sign(_hash_data(document, proof_config))
    return {**document, "proof": {**proof_config, "proofValue": "z" + _b58encode(signature)}}


def verify_credential(credential: dict) -> bool:
    proof = credential.get("proof")
    if not isinstance(proof, dict) or proof.get("cryptosuite") != CRYPTOSUITE:
        return False
    if proof.get("verificationMethod") != f"{issuer_id()}#key-1":
        return False
    proof_value = proof.get("proofValue", "")
    if not proof_value.startswith("z"):
        return False
    valid_from = credential.get("validFrom")
    if valid_from is not None:
        if not isinstance(valid_from, str):
            return False
        try:
            vf = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
        except ValueError:
            return False
        if vf.tzinfo is None:
            vf = vf.replace(tzinfo=UTC)
        if vf > datetime.now(UTC):
            return False
    document = {k: v for k, v in credential.items() if k != "proof"}
    proof_config = {k: v for k, v in proof.items() if k != "proofValue"}
    try:
        _public_key_obj().verify(_b58decode(proof_value[1:]), _hash_data(document, proof_config))
        return True
    except (InvalidSignature, ValueError):
        return False


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_sd_jwt(subject_id: str, claims: dict) -> tuple[str, dict[str, str]]:
    """SD-JWT (salted hashes, EdDSA). Every claim is hidden behind `_sd` until the holder discloses it.

    Returns the issuer JWT and the disclosure for each claim name. The event title can be one of the
    claims and still stay out of a presentation.
    """
    disclosures: dict[str, str] = {}
    hashes: list[str] = []
    for name in sorted(claims):
        salt = secrets.token_urlsafe(16)
        disclosure = _b64url(_jcs([salt, name, claims[name]]))
        disclosures[name] = disclosure
        hashes.append(_b64url(hashlib.sha256(disclosure.encode()).digest()))
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "iss": issuer_id(), "sub": f"urn:uuid:{subject_id}", "iat": now, "exp": now + 86400 * 365,
        "_sd_alg": "sha-256", "_sd": sorted(hashes),
    }
    header = {"alg": "EdDSA", "typ": "sd-jwt", "kid": f"{issuer_id()}#key-1"}
    signing_input = f"{_b64url(_jcs(header))}.{_b64url(_jcs(payload))}".encode()
    token = signing_input.decode() + "." + _b64url(_private_key().sign(signing_input))
    return token, disclosures


def present_sd_jwt(token: str, disclosures: dict[str, str], keep: set[str]) -> str:
    """A presentation is the issuer JWT, the chosen disclosures, and a trailing tilde."""
    chosen = [disclosures[name] for name in sorted(keep)]
    return "~".join([token, *chosen, ""])


def verify_sd_jwt(presentation: str) -> dict | None:
    """The revealed claims, or None when the signature or a disclosure hash does not hold.

    A claim that was not attached is absent from the result. The hash in `_sd` does not reveal it.
    """
    pieces = presentation.split("~")
    if len(pieces) < 2 or pieces[-1] != "":
        return None
    token, attached = pieces[0], pieces[1:-1]
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        _public_key_obj().verify(_b64url_decode(signature_b64), f"{header_b64}.{payload_b64}".encode())
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except (InvalidSignature, ValueError, json.JSONDecodeError):
        return None
    if header.get("alg") != "EdDSA" or payload.get("_sd_alg") != "sha-256":
        return None
    if header.get("kid") != f"{issuer_id()}#key-1":
        return None
    digest_set = set(payload.get("_sd") or [])
    revealed: dict = {}
    for disclosure in attached:
        digest = _b64url(hashlib.sha256(disclosure.encode()).digest())
        if digest not in digest_set:
            return None
        try:
            decoded = json.loads(_b64url_decode(disclosure))
            _salt, name, value = decoded
        except (ValueError, json.JSONDecodeError, TypeError):
            return None
        if not isinstance(name, str):
            return None
        revealed[name] = value
    return revealed
