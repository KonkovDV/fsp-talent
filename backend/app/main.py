import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.docs import install_docs
from app.api.errors import install_error_handlers
from app.api.v1.router import api_router
from app.core.config import PUBLISHED_SECRETS, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.SECRET_KEY in PUBLISHED_SECRETS:
        raise RuntimeError(
            "SECRET_KEY is a published placeholder and SECRET_KEY_FILE is not writable. "
            "Set a private value in .env: python -c \"import secrets; print(secrets.token_hex(32))\"")
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


@app.middleware("http")
async def request_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
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
