from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
    adapter = get_fsp_adapter()
    if not await adapter.verify_secret(body.fsp_id, body.fsp_secret):
        raise HTTPException(400, "Неверные учётные данные ФСП")
    if await db.scalar(select(Participant).where(Participant.fsp_id == body.fsp_id)):
        raise HTTPException(409, "Участник уже зарегистрирован")
    data = await adapter.fetch_participant(body.fsp_id)
    if data is None:
        raise HTTPException(400, "Протоколы ФСП не найдены")
    participant = await ingest_from_fsp(db, data)
    await rebuild_profile(db, participant)
    await db.commit()
    return _tokens(str(participant.id), "participant")


@router.post("/participant/token", response_model=TokenOut)
async def login_participant(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    if not await get_fsp_adapter().verify_secret(form.username, form.password):
        raise HTTPException(401, "Неверные учётные данные")
    participant = await db.scalar(select(Participant).where(Participant.fsp_id == form.username))
    if not participant:
        raise HTTPException(401, "Сначала зарегистрируйтесь")
    return _tokens(str(participant.id), "participant")


class EmployerRegister(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    inn: str | None = Field(None, pattern=r"^\d{10}(\d{2})?$")
    website: str | None = Field(None, max_length=200)


@router.post("/employer/register", response_model=TokenOut, status_code=201)
async def register_employer(body: EmployerRegister, db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(Employer).where(Employer.email == body.email)):
        raise HTTPException(409, "Email уже зарегистрирован")
    try:
        password_hash = hash_password(body.password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    employer = Employer(company_name=body.company_name, email=body.email, password_hash=password_hash,
                        inn=body.inn, website=body.website)
    db.add(employer)
    try:
        await db.flush()
    except IntegrityError as e:
        raise HTTPException(409, "Email уже зарегистрирован") from e
    await db.commit()
    return _tokens(str(employer.id), "employer")


@router.post("/employer/token", response_model=TokenOut)
async def login_employer(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    employer = await db.scalar(select(Employer).where(Employer.email == form.username))
    if not employer or not verify_password(form.password, employer.password_hash):
        raise HTTPException(401, "Неверные учётные данные")
    return _tokens(str(employer.id), "employer")
