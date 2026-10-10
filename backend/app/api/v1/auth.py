"""Accounts for both roles: email + password, confirmed by a code or link from the letter (TZ 2.2 п.4).

A candidate does not need FSP history to register. FSP ID is the Federation's single entry point, so a
candidate can also sign in with it (OIDC code flow + PKCE, /auth/fsp/*): an existing linked account gets its
tokens; a new person gets an account built from the FSP registry only after accepting the required consents.
An account linked to FSP ID in the profile (/candidates/me/fsp/*) signs in the same way.
"""
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_any_auth
from app.api.errors import ApiError
from app.core.config import settings
from app.core.csrf import CSRF_COOKIE, attach_csrf, check_csrf, clear_csrf
from app.core.database import get_db
from app.core.demo_guard import is_protected, reject_protected, reject_reserved
from app.core.ratelimit import RateLimitUnavailable, too_many
from app.core.redis_client import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    epochs_match,
    hash_password,
    next_refresh_nonce,
    password_matches,
    password_needs_rehash,
    verify_password,
)
from app.models import (
    AccessLog,
    Application,
    CategoryAssignment,
    Consent,
    Employer,
    EmployerTask,
    Offer,
    Participant,
    Result,
    Skill,
    TaskSubmission,
    Vacancy,
)
from app.services.account_export import (
    employer_record,
    participant_record,
    password_change_problem,
    without_secrets,
)
from app.services.fsp import identity as fsp_identity
from app.services.fsp.mock import get_fsp_adapter
from app.services.fsp.registry import FSPRegistryError
from app.services.guest import guest_expired, new_guest
from app.services.identity import (
    check_required_consents,
    check_resend_allowed,
    consume_code,
    consume_token,
    give_consent,
    issue_code,
    normalize_email,
    send_code,
    visitor_ip,
)
from app.services.inn import inn_is_valid
from app.services.login_lock import next_failure, still_locked
from app.services.privacy import contacts_allowed
from app.services.profile import ingest_from_fsp, rebuild_profile
from app.services.resumes import extras as resume_extras
from app.services.resumes import out as resume_out

router = APIRouter(prefix="/auth", tags=["auth"])

Role = Literal["participant", "employer"]


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: Role | None = None
    guest_until: str | None = None


class VerificationSent(BaseModel):
    status: Literal["verification_sent"] = "verification_sent"
    email: str
    role: Role
    expires_in_minutes: int
    resend_after_seconds: int = 60
    # Only on a demo stand with DEMO_MODE and DEMO_SHOW_CODE: letters do not leave the stand.
    demo_code: str | None = None


def _tokens(subject: str, role: str, epoch: int = 0, nonce: int = 0) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(subject, role, epoch),
        refresh_token=create_refresh_token(subject, role, epoch, nonce),
        role=role,
    )


def _account_tokens(account, role: str) -> TokenOut:
    return _tokens(
        str(account.id), role, int(account.token_epoch or 0), int(account.refresh_nonce or 0),
    )


REFRESH_COOKIE = "fsp_refresh"
FSP_SIGNIN_COOKIE = "fsp_signin"
FSP_SIGNIN_PATH = "/api/v1/auth/fsp"


def attach_signin_binder(response: Response, binder: str) -> None:
    """Binds the FSP ID login to the browser that started it. JavaScript cannot read the cookie."""
    response.set_cookie(
        key=FSP_SIGNIN_COOKIE,
        value=binder,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=fsp_identity.STATE_TTL_S,
        path=FSP_SIGNIN_PATH,
    )


def clear_signin_binder(response: Response) -> None:
    response.delete_cookie(FSP_SIGNIN_COOKIE, path=FSP_SIGNIN_PATH)


def _refresh_cookie_flags() -> dict:
    return {"path": "/api/v1/auth", "secure": settings.COOKIE_SECURE, "httponly": True, "samesite": "lax"}


def attach_refresh(response: Response, token: str) -> None:
    """The refresh token lives in an HttpOnly cookie. JavaScript does not receive it."""
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **_refresh_cookie_flags(),
    )


def clear_refresh(response: Response) -> None:
    """Remove the refresh cookie with the same flags it was stored with.

    A deletion that leaves out Secure does not replace a Secure cookie, so the browser keeps it.
    """
    response.delete_cookie(REFRESH_COOKIE, **_refresh_cookie_flags())


def browser_tokens(tokens: TokenOut) -> TokenOut:
    return tokens.model_copy(update={"refresh_token": ""})


def deliver(response: Response, tokens: TokenOut) -> TokenOut:
    attach_refresh(response, tokens.refresh_token)
    attach_csrf(response)
    return browser_tokens(tokens)


def presented_refresh(body: str | None, cookie: str | None) -> str | None:
    """An API client may send the token. The browser sends only the cookie."""
    text = (body or "").strip()
    if text:
        return text
    baked = (cookie or "").strip()
    return baked or None


async def _limit(bucket: str, identity: str, limit: int = 5) -> None:
    try:
        blocked = await too_many(f"auth:{bucket}:{identity.strip().lower()}", limit=limit, fail_closed=True)
    except RateLimitUnavailable:
        raise ApiError(503, "unavailable",
                       "Проверка попыток входа временно недоступна. Повторите через минуту.") from None
    if blocked:
        raise ApiError(429, "rate_limited", "Слишком много попыток. Подождите минуту.")


async def _charge_registration(request: Request, email: str, role: str) -> None:
    """Per address and per IP. A shared counter is not used: one script must not close the form."""
    from app.services.identity import visitor_ip
    await _limit(f"register:{role}", email)
    await _limit("register-ip", visitor_ip(request), limit=10)


def _password_hash(password: str) -> str:
    try:
        return hash_password(password)
    except ValueError as e:
        raise ApiError(422, "validation_error", "Пароль длиннее 72 байт") from e


def repeat_registration(account) -> bool:
    """The address already has an account, and the mailbox has not confirmed it yet.

    A later registration must not replace the password or the profile. The letter is delivered
    to that mailbox either way, so the person who opens it would otherwise confirm a password
    chosen by someone else.
    """
    return account is not None and account.email_verified_at is None


async def _account(db: AsyncSession, role: str, email: str):
    model = Participant if role == "participant" else Employer
    from app.services.field_cipher import email_is
    return await db.scalar(select(model).where(email_is(model, email)))


async def _send_verification(db: AsyncSession, role: str, account, email: str) -> VerificationSent:
    code, token = await issue_code(db, role, account.id, email, "verify")
    await db.commit()
    await send_code(email, role, "verify", code, token)
    shown = code if settings.DEMO_MODE and settings.DEMO_SHOW_CODE else None
    return VerificationSent(email=email, role=role, expires_in_minutes=settings.EMAIL_CODE_TTL_MINUTES,
                            demo_code=shown)


# ── registration ────────────────────────────────────────────────────────────

class ParticipantRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str | None = Field(None, max_length=200)
    # Data minimisation: we ask "18 or older", not the birth date. A linked FSP account brings the date.
    is_adult: bool
    # Under 18: registration is open from 15; the card waits for the guardian's consent (services/guardian.py).
    age_15_17: bool = False
    consents: list[str] = Field(default_factory=list, max_length=10)


@router.post("/participant/register", response_model=VerificationSent, status_code=202)
async def register_participant(body: ParticipantRegister, request: Request, db: AsyncSession = Depends(get_db)):
    email = normalize_email(body.email)
    reject_reserved(email)
    if not body.is_adult and not body.age_15_17:
        raise ApiError(422, "too_young", "Регистрация открыта с 15 лет")
    check_required_consents("participant", body.consents)
    await _charge_registration(request, email, "participant")
    p = await _account(db, "participant", email)
    if p is not None and p.email_verified_at is not None:
        raise ApiError(409, "email_taken")
    if repeat_registration(p):
        await check_resend_allowed(email, "verify")
        return await _send_verification(db, "participant", p, email)
    p = Participant(email=email, is_visible=True, public_profile=False)
    db.add(p)
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
    reject_reserved(email)
    check_required_consents("employer", body.consents)
    await _charge_registration(request, email, "employer")
    employer = await _account(db, "employer", email)
    if employer is not None and employer.email_verified_at is not None:
        raise ApiError(409, "email_taken")
    if repeat_registration(employer):
        await check_resend_allowed(email, "verify")
        return await _send_verification(db, "employer", employer, email)
    if body.inn is not None and not inn_is_valid(body.inn):
        raise ApiError(422, "validation_error", "ИНН не проходит контрольную сумму")
    password_hash = _password_hash(body.password)
    employer = Employer(company_name=body.company_name, email=email, password_hash=password_hash,
                        inn=body.inn, website=body.website)
    db.add(employer)
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
async def verify_email(body: VerifyIn, response: Response, db: AsyncSession = Depends(get_db)):
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
    return deliver(response, _account_tokens(account, row.subject_type))


class ResendIn(BaseModel):
    email: EmailStr
    role: Role


@router.post("/resend-verification", status_code=202)
async def resend_verification(body: ResendIn, db: AsyncSession = Depends(get_db)):
    """Always 202 for unknown or confirmed addresses, so the endpoint does not reveal who is registered."""
    email = normalize_email(body.email)
    await check_resend_allowed(email, "verify")
    account = await _account(db, body.role, email)
    answer = {"status": "verification_sent", "email": email, "role": body.role, "resend_after_seconds": 60}
    if account is not None and account.email_verified_at is None:
        sent = await _send_verification(db, body.role, account, email)
        if sent.demo_code:
            answer["demo_code"] = sent.demo_code
    return answer


# ── login ───────────────────────────────────────────────────────────────────

async def _login(db: AsyncSession, role: str, form: OAuth2PasswordRequestForm) -> TokenOut:
    email = normalize_email(form.username)
    # The printed demo account is the one the interface suite signs in with, many times a minute.
    await _limit(role, email, limit=60 if settings.DEMO_MODE else 5)
    if "@" not in email:
        raise ApiError(401, "invalid_credentials",
                       "Здесь вход по email. По ФСП ID входите кнопкой «Войти через ФСП ID».")
    account = await _account(db, role, email)
    now = datetime.now(UTC)
    if account is not None and still_locked(account.locked_until, now):
        raise ApiError(429, "rate_limited", "Вход закрыт на 15 минут после нескольких неверных паролей.")
    stored = account.password_hash if account is not None else None
    if not password_matches(form.password, stored):
        if account is not None:
            account.failed_logins, account.locked_until = next_failure(account.failed_logins or 0, now)
            await db.commit()
        raise ApiError(401, "invalid_credentials")
    if account is not None and (account.failed_logins or account.locked_until):
        account.failed_logins = 0
        account.locked_until = None
    if password_needs_rehash(stored):
        account.password_hash = hash_password(form.password)
    if account.email_verified_at is None:
        raise ApiError(403, "email_not_verified", details={"email": email, "role": role})
    if getattr(account, "suspended_at", None) is not None:
        raise ApiError(403, "account_suspended")
    if role == "participant":
        account.last_login_at = datetime.now(UTC)
    return _account_tokens(account, role)


@router.post("/participant/token", response_model=TokenOut)
async def login_participant(response: Response, form: OAuth2PasswordRequestForm = Depends(),
                            db: AsyncSession = Depends(get_db)):
    return deliver(response, await _login(db, "participant", form))


@router.post("/employer/token", response_model=TokenOut)
async def login_employer(response: Response, form: OAuth2PasswordRequestForm = Depends(),
                         db: AsyncSession = Depends(get_db)):
    return deliver(response, await _login(db, "employer", form))


class GuestIn(BaseModel):
    role: Role
    consents: list[str] = Field(default_factory=list, max_length=10)


@router.post("/guest", response_model=TokenOut, status_code=201)
async def guest_login(body: GuestIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Demo stand only: an empty account for 48 hours without a mailbox. See services/guest.py."""
    if not settings.DEMO_MODE:
        raise ApiError(404, "not_found")
    await _limit("guest", client_address(request), limit=10)
    await _limit("guest-site", "all", limit=60)
    check_required_consents(body.role, body.consents)
    account = new_guest(body.role)
    db.add(account)
    await db.flush()
    for kind in body.consents:
        await give_consent(db, body.role, account.id, kind, request)
    if body.role == "participant":
        account.last_login_at = datetime.now(UTC)
    await db.commit()
    tokens = _account_tokens(account, body.role)
    tokens.guest_until = account.guest_until.isoformat()
    return deliver(response, tokens)


# ── password reset ──────────────────────────────────────────────────────────

class ForgotIn(BaseModel):
    email: EmailStr
    role: Role


@router.post("/password/forgot", status_code=202)
async def forgot_password(body: ForgotIn, db: AsyncSession = Depends(get_db)):
    email = normalize_email(body.email)
    if is_protected(email):
        return {"status": "reset_sent", "email": email, "role": body.role}
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
async def reset_password(body: ResetIn, response: Response, db: AsyncSession = Depends(get_db)):
    email = normalize_email(body.email)
    reject_protected(email)
    await _limit("reset", email, limit=10)
    row = await consume_code(db, email, body.code, "reset", body.role)
    account = await _account(db, body.role, email)
    if account is None or account.id != row.subject_id:
        raise ApiError(400, "verification_invalid")
    account.password_hash = _password_hash(body.new_password)
    account.token_epoch = int(account.token_epoch or 0) + 1
    await db.commit()
    return deliver(response, _account_tokens(account, body.role))


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


@router.post("/password/change", response_model=TokenOut)
async def change_password(body: PasswordChangeIn, response: Response,
                          current: dict = Depends(get_any_auth), db: AsyncSession = Depends(get_db)):
    """Replace the password of the signed-in account. Other sessions of this account stop working."""
    role = current.get("role")
    if role not in ("participant", "employer"):
        raise ApiError(401, "unauthorized")
    await _limit("password-change", current["sub"], limit=5)
    model = Participant if role == "participant" else Employer
    account = await db.get(model, uuid.UUID(current["sub"]), with_for_update=True)
    if account is None or getattr(account, "deleted_at", None) is not None:
        raise ApiError(401, "unauthorized")
    reject_protected(getattr(account, "email", None))
    has_password = bool(account.password_hash)
    current_ok = has_password and verify_password(body.current_password, account.password_hash)
    same = current_ok and verify_password(body.new_password, account.password_hash)
    problem = password_change_problem(has_password, current_ok, same)
    if problem == "no_password":
        raise ApiError(409, "conflict", "У этого входа нет пароля. Войдите через ФСП ID или задайте пароль по письму.")
    if problem == "bad_current":
        raise ApiError(401, "invalid_credentials", "Текущий пароль не подошёл")
    if problem == "same":
        raise ApiError(422, "validation_error", "Новый пароль совпадает с текущим")
    account.password_hash = _password_hash(body.new_password)
    account.token_epoch = int(account.token_epoch or 0) + 1
    account.refresh_nonce = int(account.refresh_nonce or 0) + 1
    await db.commit()
    return deliver(response, _account_tokens(account, role))


# ── tokens ──────────────────────────────────────────────────────────────────

class RefreshIn(BaseModel):
    refresh_token: str | None = None


def account_can_refresh(account) -> bool:
    """A refresh token dies with the account. An erased profile must not mint a new access token."""
    return (
        account is not None
        and getattr(account, "deleted_at", None) is None
        and getattr(account, "suspended_at", None) is None
        and not guest_expired(account)
    )


def _grace_key(role: str, subject: str) -> str:
    return f"refresh:grace:{role}:{subject}"


async def refresh_grace_open(role: str, subject: str) -> bool:
    """True for 30 seconds after a refresh rotated. A missing Redis keeps the stricter rule."""
    try:
        redis = await get_redis()
        return bool(await redis.get(_grace_key(role, subject)))
    except Exception:
        return False


async def remember_refresh(role: str, subject: str) -> None:
    try:
        redis = await get_redis()
        await redis.set(_grace_key(role, subject), "1", ex=30)
    except Exception:
        return


@router.post("/refresh", response_model=TokenOut)
async def refresh(response: Response, request: Request, body: RefreshIn | None = None,
                  db: AsyncSession = Depends(get_db)):
    """Обновить access-токен. Браузер присылает HttpOnly-cookie, клиент API — тело запроса."""
    body_token = None if body is None else body.refresh_token
    raw = presented_refresh(body_token, request.cookies.get(REFRESH_COOKIE))
    if raw and not (body_token or "").strip():
        check_csrf(request.cookies.get(CSRF_COOKIE), request.headers.get("x-csrf-token"))
    if not raw:
        raise ApiError(401, "unauthorized")
    try:
        payload = decode_refresh_token(raw)
    except ValueError as e:
        raise ApiError(401, "unauthorized", str(e)) from e
    role = payload.get("role")
    model = Participant if role == "participant" else Employer if role == "employer" else None
    account = None
    if model is not None:
        try:
            account = await db.get(model, uuid.UUID(payload["sub"]), with_for_update=True)
        except ValueError:
            account = None
    if not account_can_refresh(account) or not epochs_match(payload.get("ep"), account.token_epoch):
        raise ApiError(401, "unauthorized")
    current = int(account.refresh_nonce or 0)
    nxt = next_refresh_nonce(payload.get("rn"), current)
    if nxt is None:
        # The refresh from the previous second is the other tab, not a stolen token.
        # Anything older, or the same gap after the grace window, closes every session.
        presented = payload.get("rn")
        if (
            presented is not None
            and int(presented) == current - 1
            and await refresh_grace_open(str(role), str(payload["sub"]))
        ):
            raise ApiError(401, "refresh_superseded")
        if presented is not None and int(presented) < current:
            account.token_epoch = int(account.token_epoch or 0) + 1
            await db.commit()
        raise ApiError(401, "unauthorized")
    account.refresh_nonce = nxt
    await remember_refresh(str(role), str(payload["sub"]))
    return deliver(response, _tokens(payload["sub"], role, int(account.token_epoch or 0), nxt))


@router.post("/logout")
async def logout(response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    """Сбросить refresh-cookie и погасить текущее поколение refresh на сервере.

    Access-токен в браузере гасит сам клиент. Украденный refresh того же поколения
    после выхода больше не обменивается.
    """
    raw = presented_refresh(None, request.cookies.get(REFRESH_COOKIE))
    if raw:
        check_csrf(request.cookies.get(CSRF_COOKIE), request.headers.get("x-csrf-token"))
        try:
            payload = decode_refresh_token(raw)
        except ValueError:
            payload = None
        role = payload.get("role") if payload else None
        model = Participant if role == "participant" else Employer if role == "employer" else None
        if payload and model is not None:
            try:
                account = await db.get(model, uuid.UUID(payload["sub"]))
            except ValueError:
                account = None
            if (
                account is not None
                and epochs_match(payload.get("ep"), account.token_epoch)
                and next_refresh_nonce(payload.get("rn"), int(account.refresh_nonce or 0)) is not None
            ):
                account.refresh_nonce = int(account.refresh_nonce or 0) + 1
                await db.commit()
    clear_refresh(response)
    clear_csrf(response)
    return {"status": "signed_out"}


@router.get("/me")
async def whoami(current: dict = Depends(get_any_auth)):
    """Токен-интроспекция: возвращает sub и role."""
    return {"sub": current["sub"], "role": current.get("role")}


@router.get("/me/export")
async def export_my_data(current: dict = Depends(get_any_auth), db: AsyncSession = Depends(get_db)):
    """The signed-in person's own data. Nothing from other accounts, and no secrets."""
    role = current.get("role")
    subject = uuid.UUID(current["sub"])
    if role == "participant":
        person = await db.get(Participant, subject)
        if person is None or person.deleted_at is not None:
            raise ApiError(404, "not_found", "Профиль не найден")
        skills = list(await db.scalars(select(Skill).where(Skill.participant_id == person.id)))
        category = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == person.id))
        consents = list(await db.scalars(select(Consent).where(
            Consent.subject_type == "participant", Consent.subject_id == person.id)))
        offers = list((await db.scalars(
            select(Offer).where(Offer.candidate_id == person.id).options(selectinload(Offer.employer)))).all())
        results = list(await db.scalars(select(Result).where(Result.participant_id == person.id)))
        applications = list((await db.scalars(
            select(Application).where(Application.candidate_id == person.id).options(
                selectinload(Application.vacancy)))).all())
        submissions = list(await db.scalars(
            select(TaskSubmission).where(TaskSubmission.participant_id == person.id)))
        task_ids = [row.task_id for row in submissions]
        titled = {row.id: row for row in await db.scalars(
            select(EmployerTask).where(EmployerTask.id.in_(task_ids)))} if task_ids else {}
        for row in submissions:
            row.task = titled.get(row.task_id)
        tasks = submissions
        access = list((await db.scalars(
            select(AccessLog).where(AccessLog.participant_id == person.id).options(
                selectinload(AccessLog.employer)))).all())
        payload = participant_record(
            person, skills, category, consents, offers, results, applications, tasks, access)
        payload["resumes"] = [resume_out(row) for row in await resume_extras(db, person.id)]
        filename = "moi-dannye.json"
    elif role == "employer":
        company = await db.get(Employer, subject)
        if company is None:
            raise ApiError(404, "not_found", "Компания не найдена")
        consents = list(await db.scalars(select(Consent).where(
            Consent.subject_type == "employer", Consent.subject_id == company.id)))
        vacancies = list(await db.scalars(select(Vacancy).where(Vacancy.employer_id == company.id)))
        offers = list((await db.scalars(
            select(Offer).where(Offer.employer_id == company.id).options(selectinload(Offer.candidate)))).all())
        names_ok = {}
        for offer in offers:
            if offer.candidate is not None:
                names_ok[offer.candidate_id] = await contacts_allowed(db, offer.candidate)
        payload = employer_record(company, consents, vacancies, offers, names_ok)
        filename = "dannye-kompanii.json"
    else:
        raise ApiError(401, "unauthorized")
    body = without_secrets(payload)
    return JSONResponse(body, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    })


# ── sign-in by FSP ID ───────────────────────────────────────────────────────

class FspSignInCallback(BaseModel):
    code: str = Field(min_length=8, max_length=2048)
    state: str = Field(min_length=8, max_length=200)


class FspSignUpIn(BaseModel):
    ticket: str = Field(min_length=20, max_length=200)
    consents: list[str] = Field(default_factory=list, max_length=10)


def client_address(request: Request) -> str:
    """The visitor's address. A public socket ignores X-Real-IP, so the header cannot spoof the limit."""
    return visitor_ip(request)


_client_ip = client_address


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
async def fsp_signin_authorize(request: Request, response: Response):
    """Start signing in by FSP ID: the address of the provider's login page. No platform session needed."""
    await _limit("fsp-signin", client_address(request), limit=20)
    started = await fsp_identity.start_signin()
    attach_signin_binder(response, started.binder)
    return {"authorize_url": started.authorize_url, "provider": fsp_identity.get_fsp_id_provider().name}


@router.post("/fsp/callback")
async def fsp_signin_callback(body: FspSignInCallback, request: Request, response: Response,
                              db: AsyncSession = Depends(get_db)):
    """Exchange the code. A linked account signs in; a new person must accept the consents first.

    The cookie set at authorize must come back. A link opened in another browser is refused.
    """
    clear_signin_binder(response)
    try:
        fsp_id = await fsp_identity.finish_signin(body.code, body.state, binder=request.cookies.get(FSP_SIGNIN_COOKIE))
    except fsp_identity.FspIdError as e:
        raise ApiError(400, "fsp_invalid", "Вход через ФСП ID не подтверждён, начните вход заново") from e
    account = await _linked(db, fsp_id)
    if account is not None:
        tokens = deliver(response, _account_tokens(account, "participant"))
        return {"status": "signed_in", **tokens.model_dump()}
    data = await _registry(fsp_id)
    # The registry data is shown so the person sees whose account is about to be created; nothing is stored yet.
    return {"status": "needs_consent", "ticket": await fsp_identity.issue_ticket(fsp_id),
            "fsp_id": fsp_id, "display_name": data.display_name, "region": data.region,
            "results": len(data.results)}


@router.post("/fsp/signup", response_model=TokenOut)
async def fsp_signin_signup(body: FspSignUpIn, request: Request, response: Response,
                            db: AsyncSession = Depends(get_db)):
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
    return deliver(response, _account_tokens(account, "participant"))
