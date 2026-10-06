import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, epochs_match
from app.models import Employer, Participant

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/participant/token")


def _subject(payload: dict) -> dict:
    try:
        uuid.UUID(str(payload.get("sub")))
    except ValueError as e:
        raise ValueError("Invalid token") from e
    return payload


async def _open_account(db: AsyncSession, payload: dict):
    """The token's epoch must still match the account. A password reset closes older tokens."""
    role = payload.get("role")
    model = Participant if role == "participant" else Employer if role == "employer" else None
    if model is None:
        raise ValueError("Wrong role")
    try:
        account = await db.get(model, uuid.UUID(str(payload["sub"])))
    except ValueError as e:
        raise ValueError("Invalid token") from e
    if account is None or getattr(account, "deleted_at", None) is not None:
        raise ValueError("Account is closed")
    if not epochs_match(payload.get("ep"), account.token_epoch):
        raise ValueError("Session was closed")
    return account


async def get_current_participant(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(token)
        if payload.get("role") != "participant":
            raise ValueError("Wrong role")
        await _open_account(db, payload)
        return _subject(payload)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")


async def get_current_employer(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(token)
        if payload.get("role") != "employer":
            raise ValueError("Wrong role")
        await _open_account(db, payload)
        return _subject(payload)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")


async def get_any_auth(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = _subject(decode_token(token))
        await _open_account(db, payload)
        return payload
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
