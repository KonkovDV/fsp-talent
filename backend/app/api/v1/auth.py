from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.ratelimit import too_many
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models import Employer, Participant
from app.services.fsp.mock import get_fsp_adapter
from app.services.profile import ingest_from_fsp, rebuild_profile

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _tokens(subject: str, role: str) -> TokenOut:
    return TokenOut(access_token=create_access_token(subject, role), refresh_token=create_refresh_token(subject, role))


class ParticipantRegister(BaseModel):
    fsp_id: str = Field(min_length=3, max_length=64)
    fsp_secret: str = Field(min_length=1, max_length=200)


@router.post("/participant/register", response_model=TokenOut, status_code=201)
async def register_participant(body: ParticipantRegister, db: AsyncSession = Depends(get_db)):
    # FIX BUG-05: use role-specific bucket prefix to avoid collision with employer register bucket.
    # auth:register:participant:{id} vs auth:register:employer:{id} are distinct namespaces.
    await _limit("register:participant", body.fsp_id)
    await _limit("register-site", "all", limit=20)
    adapter = get_fsp_adapter()
    if not await adapter.verify_secret(body.fsp_id, body.fsp_secret):
        raise HTTPException(400, "\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0435 \u0443\u0447\u0451\u0442\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0424\u0421\u041f")
    # Optimistic check (non-locking): avoids FSP round-trip for already-registered users.
    # A concurrent duplicate registration is caught below by the IntegrityError handler.
    if await db.scalar(select(Participant).where(Participant.fsp_id == body.fsp_id)):
        raise HTTPException(409, "\u0423\u0447\u0430\u0441\u0442\u043d\u0438\u043a \u0443\u0436\u0435 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u043d")
    data = await adapter.fetch_participant(body.fsp_id)
    if data is None:
        raise HTTPException(400, "\u041f\u0440\u043e\u0442\u043e\u043a\u043e\u043b\u044b \u0424\u0421\u041f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b")
    participant = await ingest_from_fsp(db, data)
    await rebuild_profile(db, participant)
    # FIX BUG-I: TOCTOU race on fsp_id UNIQUE constraint.
    # Two concurrent requests for the same fsp_id both pass the SELECT check above,
    # both call ingest_from_fsp, and the second commit raises IntegrityError on the
    # participants.fsp_id UNIQUE index. Without this handler the caller gets HTTP 500.
    # Correct response: 409 Conflict. db.rollback() is required before re-raising so
    # the session is not left in a broken state.
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "\u0423\u0447\u0430\u0441\u0442\u043d\u0438\u043a \u0443\u0436\u0435 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u043d")
    return _tokens(str(participant.id), "participant")


async def _limit(bucket: str, identity: str, limit: int = 5) -> None:
    # Keyed by account, not by IP: behind nginx every visitor shares one address.
    if await too_many(f"auth:{bucket}:{identity.strip().lower()}", limit=limit):
        raise HTTPException(429, "\u0421\u043b\u0438\u0448\u043a\u043e\u043c \u043c\u043d\u043e\u0433\u043e \u043f\u043e\u043f\u044b\u0442\u043e\u043a. \u041f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435 \u043c\u0438\u043d\u0443\u0442\u0443.")


@router.post("/participant/token", response_model=TokenOut)
async def login_participant(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    await _limit("participant", form.username)
    if not await get_fsp_adapter().verify_secret(form.username, form.password):
        raise HTTPException(401, "\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0435 \u0443\u0447\u0451\u0442\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435")
    participant = await db.scalar(select(Participant).where(Participant.fsp_id == form.username))
    if not participant:
        raise HTTPException(401, "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u0443\u0439\u0442\u0435\u0441\u044c")
    return _tokens(str(participant.id), "participant")


class EmployerRegister(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    inn: str | None = Field(None, pattern=r"^\d{10}(\d{2})?$")
    website: str | None = Field(None, max_length=200)


@router.post("/employer/register", response_model=TokenOut, status_code=201)
async def register_employer(body: EmployerRegister, db: AsyncSession = Depends(get_db)):
    # FIX BUG-05: use role-specific bucket prefix
    await _limit("register:employer", body.email)
    await _limit("register-site", "all", limit=20)
    if await db.scalar(select(Employer).where(Employer.email == body.email)):
        raise HTTPException(409, "Email \u0443\u0436\u0435 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u043d")
    try:
        password_hash = hash_password(body.password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    employer = Employer(company_name=body.company_name, email=body.email, password_hash=password_hash,
                        inn=body.inn, website=body.website)
    db.add(employer)
    # FIX BUG-I (employer): same TOCTOU race on email UNIQUE constraint.
    # Two concurrent registrations for the same email both pass the SELECT check;
    # the second flush raises IntegrityError -> 500 without this handler.
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Email \u0443\u0436\u0435 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u043d")
    await db.commit()
    return _tokens(str(employer.id), "employer")


@router.post("/employer/token", response_model=TokenOut)
async def login_employer(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    await _limit("employer", form.username)
    employer = await db.scalar(select(Employer).where(Employer.email == form.username))
    if not employer or not verify_password(form.password, employer.password_hash):
        raise HTTPException(401, "\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0435 \u0443\u0447\u0451\u0442\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435")
    return _tokens(str(employer.id), "employer")
