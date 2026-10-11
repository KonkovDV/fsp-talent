from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from jwt import PyJWTError as JWTError

from app.core.config import settings

_BCRYPT_MAX_BYTES = 72
_PASSWORD_MAX_BYTES = 1024
# OWASP: Argon2id, 19 MiB, two passes, one lane. New passwords use this. Old bcrypt hashes still verify.
_HASHER = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1)
# Argon2id of a password no account uses. A missing account still pays for one check.
_UNKNOWN_PASSWORD_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$oJI0NxI3WdDWOTxk9NCu3A$GczMb2RkJnjYXtHOK13P4T6jC49WbDTxUAbOBzfV5DA"
)


def hash_password(password: str) -> str:
    if len(password.encode()) > _PASSWORD_MAX_BYTES:
        raise ValueError("Password too long")
    return _HASHER.hash(password)


def password_needs_rehash(hashed: str | None) -> bool:
    """True for a bcrypt hash and for Argon2id written with older parameters."""
    if not hashed or not hashed.startswith("$argon2"):
        return bool(hashed)
    return _HASHER.check_needs_rehash(hashed)


def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("$argon2"):
        try:
            return _HASHER.verify(hashed, plain)
        except (VerifyMismatchError, VerificationError):
            return False
    pw = plain.encode()
    if len(pw) > _BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(pw, hashed.encode())
    except ValueError:
        return False


def password_matches(plain: str, hashed: str | None) -> bool:
    """True when this hash is the password.

    A missing hash still runs Argon2id on a dummy hash, so the two cases take the same time.
    """
    ok = verify_password(plain, hashed or _UNKNOWN_PASSWORD_HASH)
    return bool(hashed) and ok


def create_token(data: dict, expire_minutes: int) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + timedelta(minutes=expire_minutes)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def epochs_match(token_epoch: int | None, account_epoch: int | None) -> bool:
    """A token from before a password reset must not open a new session."""
    return int(token_epoch or 0) == int(account_epoch or 0)


def create_access_token(subject: str, role: str, epoch: int = 0) -> str:
    return create_token(
        {"sub": subject, "role": role, "type": "access", "ep": int(epoch)},
        settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def create_refresh_token(subject: str, role: str, epoch: int = 0, nonce: int = 0) -> str:
    return create_token(
        {"sub": subject, "role": role, "type": "refresh", "ep": int(epoch), "rn": int(nonce)},
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60,
    )


def next_refresh_nonce(token_nonce: int | None, account_nonce: int) -> int | None:
    """The next refresh generation, or None when this token is no longer the current one.

    A token issued before generations existed is accepted once, and only while the account is still
    on generation 0. After that exchange the old token dies.
    """
    current = int(account_nonce or 0)
    if token_nonce is None:
        return current + 1 if current == 0 else None
    if int(token_nonce) != current:
        return None
    return current + 1


def decode_token(token: str) -> dict:
    """Decode and validate an ACCESS token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as e:
        raise ValueError("Invalid token") from e
    if payload.get("type") != "access":
        raise ValueError("Access token required")
    return payload


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a REFRESH token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as e:
        raise ValueError("Invalid refresh token") from e
    if payload.get("type") != "refresh":
        raise ValueError("Refresh token required")
    if "sub" not in payload or "role" not in payload:
        raise ValueError("Malformed refresh token")
    return payload
