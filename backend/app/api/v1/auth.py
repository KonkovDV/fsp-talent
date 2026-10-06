"""Accounts for both roles: email + password, confirmed by a code or link from the letter (TZ 2.2 п.4).

A candidate does not need FSP history to register. FSP ID is the Federation's single entry point, so a
candidate can also sign in with it (OIDC code flow + PKCE, /auth/fsp/*): an existing linked account gets its
tokens; a new person gets an account built from the FSP registry only after accepting the required consents.
An account linked to FSP ID in the profile (/candidates/me/fsp/*) signs in the same way.
"""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_any_auth
from app.api.errors import ApiError
from app.core.config import settings
from app.core.database import get_db
from app.core.ratelimit import RateLimitUnavailable, too_many
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models import Employer, Participant
from app.services.fsp import identity as fsp_identity
from app.services.fsp.mock import get_fsp_adapter
from app.services.fsp.registry import FSPRegistryError
from app.services.identity import (
    check_required_consents,
    check_resend_allowed,
    consume_code,
    consume_token,
    give_consent,
    issue_code,
    normalize_email,
    send_code,
)
from app.services.profile import ingest_from_fsp, rebuild_profile

router = APIRouter(prefix="/auth", tags=["auth"])

Role = Literal["participant", "employer"]


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: Role | None = None


class VerificationSent(BaseModel):
    status: Literal["verification_sent"] = "verification_sent"
    email: str
    role: Role
    expires_in_minutes: int
    resend_after_seconds: int = 60


def _tokens(subject: str, role: str) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(subject, role),
        refresh_token=create_refresh_token(subject, role),
        role=role,
    )


async def _limit(bucket: str, identity: str, limit: int = 5) -> None:
    try:
        blocked = await too_many(f"auth:{bucket}:{identity.strip().lower()}", limit=limit, fail_closed=True)
    except RateLimitUnavailable:
        raise ApiError(503, "unavailable",
                       "Проверка попыток входа временно недоступна. Повторите через минуту.") from None
    if blocked:
        raise ApiError(429, "rate_limited", "Слишком много попыток. Подождите минуту.")


def _password_hash(password: str) -> str:
    try:
        return hash_password(password)
    except ValueError as e:
        raise ApiError(422, "validation_error", "Пароль длиннее 72 байт") from e


async def _account(db: AsyncSession, role: str, email: str):
    model = Participant if role == "participant" else Employer
    return await db.scalar(select(model).where(model.email == email))


async def _send_verification(db: AsyncSession, role: str, account, email: str) -> VerificationSent:
    code, token = await issue_code(db, role, account.id, email, "verify")
    await db.commit()
    await send_code(email, role, "verify", code, token)
    return VerificationSent(email=email, role=role, expires_in_minutes=settings.EMAIL_CODE_TTL_MINUTES)


# ── registration ────────────────────────────────────────────────────────────

class ParticipantRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str | None = Field(None, max_length=200)
    # Data minimisation: we ask "18 or older", not the birth date. A linked FSP account brings the date.
    is_adult: bool
    consents: list[str] = Field(default_factory=list, max_length=10)


@router.post("/participant/register", response_model=VerificationSent, status_code=202)
async def register_participant(body: ParticipantRegister, request: Request, db: AsyncSession = Depends(get_db)):
    email = normalize_email(body.email)
    await _limit("register:participant", email)
    await _limit("register-site", "all", limit=30)
    check_required_consents("participant", body.consents)
    p = await _account(db, "participant", email)
    if p is not None and p.email_verified_at is not None:
        raise ApiError(409, "email_taken")
    if p is not None:
        await check_resend_allowed(email, "verify")
    if p is None:
        p = Participant(email=email, is_visible=True, public_profile=False)
        db.add(p)
    # An unconfirmed account belongs to nobody yet: the latest registration sets the password.
    p.password_hash = _password_hash(body.password)
    p.display_name = (body.display_name or "").strip() or p.display_name
    p.is_minor = not body.is_adult
    try:
        await db.flush()
    except IntegrityError as e:   # a parallel registration of the same email won the race
        await db.rollback()
        raise ApiError(409, "email_taken") from e
    for kind in body.consents:
        await give_consent(db, "participant", p.id, kind, request)
    return await _send_verification(db, "participant", p, email)


class EmployerRegister(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    inn: str | None = Field(None, pattern=r"^\d{10}(\d{2})?$")
    website: str | None = Field(None, max_length=200)
    consents: list[str] = Field(default_factory=list, max_length=10)


@router.post("/employer/register", response_model=VerificationSent, status_code=202)
async def register_employer(body: EmployerRegister, request: Request, db: AsyncSession = Depends(get_db)):
    email = normalize_email(body.email)
    await _limit("register:employer", email)
    await _limit("register-site", "all", limit=30)
    check_required_consents("employer", body.consents)
    employer = await _account(db, "employer", email)
    if employer is not None and employer.email_verified_at is not None:
        raise ApiError(409, "email_taken")
    if employer is not None:
        await check_resend_allowed(email, "verify")
    password_hash = _password_hash(body.password)
    if employer is None:
        employer = Employer(company_name=body.company_name, email=email, password_hash=password_hash)
        db.add(employer)
    employer.company_name, employer.password_hash = body.company_name, password_hash
    employer.inn, employer.website = body.inn, body.website
    try:
        await db.flush()
    except IntegrityError as e:   # a parallel registration of the same email won the race
        await db.rollback()
        raise ApiError(409, "email_taken") from e
    for kind in body.consents:
        await give_consent(db, "employer", employer.id, kind, request)
    return await _send_verification(db, "employer", employer, email)


# ── confirmation ────────────────────────────────────────────────────────────

class VerifyIn(BaseModel):
    email: EmailStr | None = None
    code: str | None = Field(None, pattern=r"^\s*\d{6}\s*$")
    token: str | None = Field(None, min_length=20, max_length=200)
    role: Role | None = None

    @model_validator(mode="after")
    def _one_way(self):
        if not self.token and not (self.email and self.code):
            raise ValueError("Нужен код из письма вместе с email или токен из ссылки")
        return self


@router.post("/verify-email", response_model=TokenOut)
async def verify_email(body: VerifyIn, db: AsyncSession = Depends(get_db)):
    if body.token:
        row = await consume_token(db, body.token)
    else:
        email = normalize_email(body.email)
        await _limit("verify", email, limit=10)
        row = await consume_code(db, email, body.code, "verify", body.role)
    model = Participant if row.subject_type == "participant" else Employer
    account = await db.get(model, row.subject_id, with_for_update=True)
    if account is None or account.email != row.email:
        raise ApiError(400, "verification_invalid")
    if account.email_verified_at is None:
        account.email_verified_at = datetime.now(UTC)
        if row.subject_type == "participant":
            # Only confirmed accounts enter the employer search index.
            await rebuild_profile(db, account)
    await db.commit()
    return _tokens(str(account.id), row.subject_type)


class ResendIn(BaseModel):
    email: EmailStr
    role: Role


@router.post("/resend-verification", status_code=202)
async def resend_verification(body: ResendIn, db: AsyncSession = Depends(get_db)):
    """Always 202 for unknown or confirmed addresses, so the endpoint does not reveal who is registered."""
    email = normalize_email(body.email)
    await check_resend_allowed(email, "verify")
    account = await _account(db, body.role, email)
    if account is not None and account.email_verified_at is None:
        await _send_verification(db, body.role, account, email)
    return {"status": "verification_sent", "email": email, "role": body.role, "resend_after_seconds": 60}


# ── login ───────────────────────────────────────────────────────────────────

async def _login(db: AsyncSession, role: str, form: OAuth2PasswordRequestForm) -> TokenOut:
    email = normalize_email(form.username)
    await _limit(role, email)
    if "@" not in email:
        raise ApiError(401, "invalid_credentials",
                       "Здесь вход по email. По ФСП ID входите кнопкой «Войти через ФСП ID».")
    account = await _account(db, role, email)
    if account is None or not account.password_hash or not verify_password(form.password, account.password_hash):
        raise ApiError(401, "invalid_credentials")
    if account.email_verified_at is None:
        raise ApiError(403, "email_not_verified", details={"email": email, "role": role})
    return _tokens(str(account.id), role)


@router.post("/participant/token", response_model=TokenOut)
async def login_participant(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    return await _login(db, "participant", form)


@router.post("/employer/token", response_model=TokenOut)
async def login_employer(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    return await _login(db, "employer", form)


# ── password reset ──────────────────────────────────────────────────────────

class ForgotIn(BaseModel):
    email: EmailStr
    role: Role


@router.post("/password/forgot", status_code=202)
async def forgot_password(body: ForgotIn, db: AsyncSession = Depends(get_db)):
    email = normalize_email(body.email)
    await check_resend_allowed(email, "reset")
    account = await _account(db, body.role, email)
    if account is not None and account.email_verified_at is not None:
        code, token = await issue_code(db, body.role, account.id, email, "reset")
        await db.commit()
        await send_code(email, body.role, "reset", code, token)
    return {"status": "reset_sent", "email": email, "role": body.role}


class ResetIn(BaseModel):
    email: EmailStr
    role: Role
    code: str = Field(pattern=r"^\s*\d{6}\s*$")
    new_password: str = Field(min_length=8, max_length=72)


@router.post("/password/reset", response_model=TokenOut)
async def reset_password(body: ResetIn, db: AsyncSession = Depends(get_db)):
    email = normalize_email(body.email)
    await _limit("reset", email, limit=10)
    row = await consume_code(db, email, body.code, "reset", body.role)
    account = await _account(db, body.role, email)
    if account is None or account.id != row.subject_id:
        raise ApiError(400, "verification_invalid")
    account.password_hash = _password_hash(body.new_password)
    await db.commit()
    return _tokens(str(account.id), body.role)


# ── tokens ──────────────────────────────────────────────────────────────────

class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10)


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn):
    """Обновить access-токен по refresh-токену (без обращения к БД)."""
    try:
        payload = decode_refresh_token(body.refresh_token)
    except ValueError as e:
        raise ApiError(401, "unauthorized", str(e)) from e
    return _tokens(payload["sub"], payload["role"])


@router.get("/me")
async def whoami(current: dict = Depends(get_any_auth)):
    """Токен-интроспекция: возвращает sub и role."""
    return {"sub": current["sub"], "role": current.get("role")}


# ── sign-in by FSP ID ───────────────────────────────────────────────────────

class FspSignInCallback(BaseModel):
    code: str = Field(min_length=8, max_length=2048)
    state: str = Field(min_length=8, max_length=200)


class FspSignUpIn(BaseModel):
    ticket: str = Field(min_length=20, max_length=200)
    consents: list[str] = Field(default_factory=list, max_length=10)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _registry(fsp_id: str):
    try:
        data = await get_fsp_adapter().fetch_participant(fsp_id)
    except FSPRegistryError as e:
        raise ApiError(503, "unavailable", "Реестр ФСП сейчас не отвечает, попробуйте позже") from e
    if data is None:
        raise ApiError(404, "fsp_not_found")
    return data


async def _linked(db: AsyncSession, fsp_id: str) -> Participant | None:
    return await db.scalar(select(Participant).where(Participant.fsp_id == fsp_id, Participant.deleted_at.is_(None)))


@router.post("/fsp/authorize")
async def fsp_signin_authorize(request: Request):
    """Start signing in by FSP ID: the address of the provider's login page. No platform session needed."""
    await _limit("fsp-signin", _client_ip(request), limit=20)
    started = await fsp_identity.start_signin()
    return {"authorize_url": started.authorize_url, "provider": fsp_identity.get_fsp_id_provider().name}


@router.post("/fsp/callback")
async def fsp_signin_callback(body: FspSignInCallback, db: AsyncSession = Depends(get_db)):
    """Exchange the code. A linked account signs in; a new person must accept the consents first."""
    try:
        fsp_id = await fsp_identity.finish_signin(body.code, body.state)
    except fsp_identity.FspIdError as e:
        raise ApiError(400, "fsp_invalid", "Вход через ФСП ID не подтверждён, начните вход заново") from e
    account = await _linked(db, fsp_id)
    if account is not None:
        return {"status": "signed_in", **_tokens(str(account.id), "participant").model_dump()}
    data = await _registry(fsp_id)
    # The registry data is shown so the person sees whose account is about to be created; nothing is stored yet.
    return {"status": "needs_consent", "ticket": await fsp_identity.issue_ticket(fsp_id),
            "fsp_id": fsp_id, "display_name": data.display_name, "region": data.region,
            "results": len(data.results)}


@router.post("/fsp/signup", response_model=TokenOut)
async def fsp_signin_signup(body: FspSignUpIn, request: Request, db: AsyncSession = Depends(get_db)):
    """Create the account from the FSP registry after the required consents (152-FZ art. 9).

    FSP ID is the identity provider: the account works without an email and a password. The person can add
    Telegram or a phone in the profile; the employer receives them only after an accepted invitation.
    """
    check_required_consents("participant", body.consents)   # before the ticket is spent
    try:
        fsp_id = await fsp_identity.take_ticket(body.ticket)
    except fsp_identity.FspIdError as e:
        raise ApiError(400, "fsp_ticket_invalid") from e
    account = await _linked(db, fsp_id)
    if account is None:
        data = await _registry(fsp_id)
        account = await ingest_from_fsp(db, data)
        account.is_visible, account.public_profile = True, False
        try:
            await db.flush()
        except IntegrityError as e:   # a parallel sign-up with the same FSP ID won the race
            await db.rollback()
            raise ApiError(409, "fsp_taken") from e
        for kind in body.consents:
            await give_consent(db, "participant", account.id, kind, request)
        await rebuild_profile(db, account)
        await db.commit()
    return _tokens(str(account.id), "participant")
