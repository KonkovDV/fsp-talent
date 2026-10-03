from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/participant/token")


async def get_current_participant(token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_token(token)
        if payload.get("role") != "participant":
            raise ValueError("Wrong role")
        return payload
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


async def get_current_employer(token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_token(token)
        if payload.get("role") != "employer":
            raise ValueError("Wrong role")
        return payload
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


async def get_any_auth(token: str = Depends(oauth2_scheme)):
    try:
        return decode_token(token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
