import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/participant/token")


def _subject(payload: dict) -> dict:
    try:
        uuid.UUID(str(payload.get("sub")))
    except ValueError as e:
        raise ValueError("Invalid token") from e
    return payload


async def get_current_participant(token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_token(token)
        if payload.get("role") != "participant":
            raise ValueError("Wrong role")
        return _subject(payload)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")


async def get_current_employer(token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_token(token)
        if payload.get("role") != "employer":
            raise ValueError("Wrong role")
        return _subject(payload)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")


async def get_any_auth(token: str = Depends(oauth2_scheme)):
    try:
        return _subject(decode_token(token))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
