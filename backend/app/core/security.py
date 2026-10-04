from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode()
    if len(pw) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password too long")
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    pw = plain.encode()
    if len(pw) > _BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(pw, hashed.encode())
    except ValueError:
        return False


def create_token(data: dict, expire_minutes: int) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + timedelta(minutes=expire_minutes)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    return create_token(
        {"sub": subject, "role": role, "type": "access"},
        settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def create_refresh_token(subject: str, role: str) -> str:
    return create_token(
        {"sub": subject, "role": role, "type": "refresh"},
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60,
    )


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
