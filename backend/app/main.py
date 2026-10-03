"""
FSP Talent Platform -- FastAPI application entry point.

Middleware stack (outermost to innermost)
-----------------------------------------
1. CORSMiddleware          -- allow configured origins
2. RequestIDMiddleware     -- attach X-Request-ID to every request/response
3. SlowAPI / Limiter       -- rate limiting (applied per-route via decorator)
4. Route handlers

Rate limits
-----------
* /api/v1/auth/*  : 10 requests/minute per IP  (brute-force protection)
* Default         : 60 requests/minute per IP

Health check
------------
GET /health  ->  {status, version, timestamp}  (no auth required)
GET /docs    ->  Swagger UI (always enabled; guard with network policy in prod)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import auth, candidates, employers, offers, participants, public, search
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter (SlowAPI -- thin wrapper over limits library)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FSP Talent Platform",
    version="0.3.0",
    description=(
        "Hiring marketplace for Federation of Sports Programming athletes. "
        "Privacy-first: employer search results are anonymised; "
        "contact details released only after candidate acceptance."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Attach SlowAPI state so that per-route @limiter.limit() decorators work
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and echo it in the response.

    Priority: X-Request-ID header from caller > auto-generated UUID4.
    Useful for distributed tracing across API gateway logs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(participants.router, prefix=API_PREFIX)
app.include_router(employers.router, prefix=API_PREFIX)
app.include_router(offers.router, prefix=API_PREFIX)
app.include_router(candidates.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(public.router, prefix=API_PREFIX)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["infra"], summary="Health check")
async def health() -> dict:
    """Lightweight health probe for load-balancer / k8s liveness checks."""
    return {
        "status": "ok",
        "version": app.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def _startup() -> None:
    logger.info(
        "FSP Talent Platform v%s started | mode=%s ai=%s embeddings=%s",
        app.version,
        settings.FSP_MODE,
        settings.AI_ENABLED,
        settings.EMBEDDINGS_MODE,
    )


@app.on_event("shutdown")
async def _shutdown() -> None:
    logger.info("FSP Talent Platform shutting down.")
