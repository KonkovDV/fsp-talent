import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.docs import install_docs
from app.api.errors import install_error_handlers
from app.api.v1.router import api_router
from app.core.body_limit import LimitRequestBody
from app.core.config import PUBLISHED_SECRETS, settings
from app.core.csp import POLICY
from app.core.rls import reset_rls, set_rls
from app.core.security import decode_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.SECRET_KEY in PUBLISHED_SECRETS:
        raise RuntimeError(
            "SECRET_KEY is a published placeholder and SECRET_KEY_FILE is not writable. "
            "Set a private value in .env: python -c \"import secrets; print(secrets.token_hex(32))\"")
    if not settings.DEMO_MODE and not settings.COOKIE_SECURE:
        logger.warning("COOKIE_SECURE is off while DEMO_MODE is off. The refresh cookie will travel without Secure.")
    logger.info(f"FSP Talent API v{settings.VERSION} starting (mode={settings.FSP_MODE})")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="ФСП Талант API",
    description=("ЛЦТ 2026, кейс Федерации спортивного программирования: подбор ИТ-специалистов "
                 "по подтверждённому результату. Коды ошибок: docs/API_ERRORS.md."),
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url=None,     # served by app.api.docs without a CDN, so the site CSP allows it
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


class BrowserLock(BaseHTTPMiddleware):
    """Headers a browser should see even when the API is opened without nginx."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", POLICY)
        return response


app.add_middleware(BrowserLock)
# Added last, so it runs first and can answer 413 before the body is parsed.
app.add_middleware(LimitRequestBody)


# Paths that run before a session exists. A signed-in request is never on this list: the bearer is read first.
# /api/v1/auth is not a prefix. /auth/me, /auth/me/export and /auth/password/change keep the caller's scope.
_BYPASS_EXACT = {
    "/health",
    "/openapi.json",
    "/api/v1/auth/participant/register",
    "/api/v1/auth/employer/register",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/resend-verification",
    "/api/v1/auth/participant/token",
    "/api/v1/auth/employer/token",
    "/api/v1/auth/password/forgot",
    "/api/v1/auth/password/reset",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/fsp/authorize",
    "/api/v1/auth/fsp/callback",
    "/api/v1/auth/fsp/signup",
}


def _open_path(path: str) -> bool:
    if path in _BYPASS_EXACT:
        return True
    if path == "/api/v1/public" or path.startswith("/api/v1/public/"):
        return True
    if path == "/api/v1/fsp-id-demo" or path.startswith("/api/v1/fsp-id-demo/"):
        return True
    if path == "/docs" or path.startswith("/docs/"):
        return True
    if path == "/redoc" or path.startswith("/redoc/"):
        return True
    return False


def _rls_token(request: Request):
    path = request.url.path
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        try:
            payload = decode_token(header.split(" ", 1)[1])
        except ValueError:
            payload = None
        if payload and payload.get("role") == "participant":
            return set_rls(participant_id=str(payload.get("sub") or ""))
        if payload and payload.get("role") == "employer":
            return set_rls(employer_id=str(payload.get("sub") or ""))
    if _open_path(path):
        return set_rls(bypass=True)
    return set_rls()


@app.middleware("http")
async def request_timing(request: Request, call_next):
    start = time.perf_counter()
    scope = _rls_token(request)
    try:
        response = await call_next(request)
    finally:
        reset_rls(scope)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"
    if duration_ms > 2000:
        logger.warning(f"Slow request {request.method} {request.url.path}: {duration_ms:.0f}ms")
    return response


install_error_handlers(app)
install_docs(app)
app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": settings.VERSION, "mode": settings.FSP_MODE}


@app.get("/.well-known/did.json", tags=["public"])
async def well_known_did():
    """did:web document. The key is the credential signing key. No personal data."""
    from app.services.vc.did_web import did_document
    from app.services.vc.issuer import public_key_multibase

    return did_document(settings.PUBLIC_BASE_URL, public_key_multibase())
