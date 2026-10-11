import logging
import os
import secrets
import time
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("app.core.config")

# These strings are in the repo. A token signed with either of them can be forged by anyone who cloned it.
PUBLISHED_SECRETS = frozenset({
    "",
    "change-me-32-chars-minimum-secret",
    "change-me-use-openssl-rand-hex-32",
})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    SECRET_KEY: str = "change-me-32-chars-minimum-secret"
    # Used only when SECRET_KEY is left as the placeholder: the first process generates a random key here,
    # every other process (API, worker, a seed run through `docker compose exec`) reads the same file.
    SECRET_KEY_FILE: str = "/secrets/secret_key"
    # Optional 32+ byte secret for contact encryption. Empty means the signing key is the HKDF input.
    FIELD_ENCRYPTION_KEY: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://fsp:fsp@localhost:5432/fsp_talent"
    # Superuser address used only by alembic and by the one statement that lets fsp_app log in.
    # Empty on a local run: migrations use DATABASE_URL.
    MIGRATE_DATABASE_URL: str = ""
    # When set, the API, worker and beat log in as fsp_app. Empty keeps the superuser login.
    APP_DB_PASSWORD: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    DEBUG: bool = False
    # The six-item jury trial is offered only when this is on. The demo compose turns it on.
    DEMO_MODE: bool = False
    # Moscow crontab for the nightly jury reset. An empty string turns it off, for a showing.
    DEMO_RESET_CRON: str = "10 4 * * *"
    # Public demo stand without a real mail account: the registration answer carries the confirmation code,
    # only to the person who registers. Ignored unless DEMO_MODE is on as well.
    DEMO_SHOW_CODE: bool = False
    # Addresses ending with one of these stay usable on the demo stand: password and deletion are closed.
    DEMO_PROTECTED_SUFFIXES: str = "@demo.talent,.demo"
    VERSION: str = "1.1.0"
    PUBLIC_BASE_URL: str = "http://localhost"
    CORS_ORIGINS: str = "http://localhost,http://localhost:5173"

    # Feature flags
    FSP_MODE: str = "mock"   # mock | real
    AI_ENABLED: bool = True
    EMBEDDINGS_MODE: str = "off"   # off | model (sentence-transformers, see [ai] extra)
    # off | model. A local cross-encoder name is required for model, e.g. BAAI/bge-reranker-v2-m3.
    # Empty stays off: the demo image has no weights, and the published list order stays.
    CROSS_ENCODER_MODE: str = "off"
    CROSS_ENCODER_MODEL: str = ""
    # auto uses the GPU when the process can see one. cpu and gpu force the device.
    CROSS_ENCODER_DEVICE: str = "auto"
    # legacy: a declared grade counts as 0.85 of a confirmed one.
    # expected: the grade factor is the expected relevance under the posterior of the true grade.
    # The default stays legacy until a three-seed run meets the acceptance rule.
    GRADE_MODEL: str = "legacy"

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # The refresh cookie is Secure only on HTTPS. The local stand is HTTP.
    COOKIE_SECURE: bool = False
    ALGORITHM: str = "HS256"

    # GigaChat (AI advisor). Credentials = Authorization key from developers.sber.ru
    GIGACHAT_CREDENTIALS: str = ""
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"
    GIGACHAT_MODEL: str = "GigaChat-2-Pro"
    # A different model re-reads an item draft. Empty means drafts are not requested.
    GIGACHAT_CHECK_MODEL: str = ""
    GIGACHAT_VERIFY_SSL: bool = True

    # YandexGPT (Yandex AI Studio), used when GIGACHAT_CREDENTIALS is empty. API key of a service account
    # with ai.languageModels.user on the folder. yandexgpt/latest is the older Pro 5 alias.
    YANDEX_API_KEY: str = ""
    YANDEX_FOLDER_ID: str = ""
    YANDEX_MODEL: str = "yandexgpt-5.1/latest"
    YANDEX_CHECK_MODEL: str = ""

    # Embeddings
    EMBEDDING_MODEL: str = "deepvk/USER-bge-m3"
    EMBEDDING_DIM: int = 1024

    # Practice code runs. SANDBOX_SOCKET: the sandbox container (no network, Python and Node).
    # Empty: a local child process, Python only. SANDBOX_REQUIRED refuses that fallback.
    # Secure by default: the fallback runs candidate code inside the API container next
    # to SECRET_KEY and the database, so it needs an explicit SANDBOX_REQUIRED=false (tests, laptop).
    SANDBOX_SOCKET: str = ""
    SANDBOX_TOKEN: str = ""
    SANDBOX_REQUIRED: bool = True

    # Verifiable Credentials (W3C VC 2.0, Data Integrity eddsa-jcs-2022)
    VC_PRIVATE_KEY_PATH: str = "/secrets/vc_ed25519.pem"

    # Email (TZ 2.2 п.4). console: print to the API log; file: write JSON letters to MAIL_FILE_DIR
    # (CI and smoke read codes from there); smtp: real delivery (Mailpit locally, any SMTP on the stand).
    MAIL_MODE: str = "console"   # console | file | smtp
    MAIL_FILE_DIR: str = "/tmp/fsp-talent-mail"
    MAIL_FROM: str = "FSP Talent <no-reply@fsp-talent.local>"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = False
    SMTP_SSL: bool = False
    EMAIL_CODE_TTL_MINUTES: int = 30
    # Floor for a monthly gross fork: the federal minimum wage, 27 093 ₽ from 1 January 2026
    # (Federal Law of 28.11.2025 No. 429-FZ, art. 1 of 82-FZ). Update every January.
    MIN_MONTHLY_GROSS: int = 27_093

    # FSP registry API (FSP_MODE=real): the contract we propose is in docs/FSP_INTEGRATION.md
    FSP_API_URL: str = ""
    FSP_API_KEY: str = ""

    # FSP ID login (OpenID Connect, Keycloak-compatible). mock: demo provider page on this site.
    # The bare default is oidc. mock is allowed only while DEMO_MODE is on.
    FSP_ID_MODE: str = "oidc"   # mock | oidc
    FSP_ID_ISSUER: str = ""     # https://<keycloak>/realms/<realm>, the address the browser opens
    FSP_ID_BACKEND_ISSUER: str = ""  # same realm as seen from the API container; empty uses FSP_ID_ISSUER
    FSP_ID_CLIENT_ID: str = "fsp-talent"
    FSP_ID_CLIENT_SECRET: str = ""
    FSP_ID_CLAIM: str = "fsp_id"

    @model_validator(mode="after")
    def _mocks_need_the_demo(self):
        if self.FSP_ID_MODE == "mock" and not self.DEMO_MODE:
            raise RuntimeError("FSP_ID_MODE=mock is only allowed when DEMO_MODE is on")
        if self.MAIL_MODE == "console" and not self.DEMO_MODE:
            logger.warning("MAIL_MODE=console while DEMO_MODE is off: letters are not delivered")
        return self


def _read_key(path: Path) -> str:
    # Another process may have created the file and not written it yet.
    for _ in range(50):
        key = path.read_text().strip()
        if key:
            return key
        time.sleep(0.1)
    return ""


def resolve_secret_key(s: Settings) -> None:
    """Replace a published placeholder with a private key kept next to the signing key.

    `cp .env.example .env && docker compose up` then works without editing the file, and the key is
    still unique to the installation. Without a writable directory (a bare local run) the placeholder
    stays, and the API refuses to start with a message that says what to set.
    """
    if s.SECRET_KEY not in PUBLISHED_SECRETS:
        return
    path = Path(s.SECRET_KEY_FILE)
    if path.is_file():
        s.SECRET_KEY = _read_key(path) or s.SECRET_KEY
        return
    if not path.parent.is_dir():
        return
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        s.SECRET_KEY = _read_key(path) or s.SECRET_KEY
        return
    except OSError:
        return
    key = secrets.token_hex(32)
    with os.fdopen(fd, "w") as handle:
        handle.write(key)
    s.SECRET_KEY = key


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    resolve_secret_key(s)
    return s


settings = get_settings()


def migration_database_url() -> str:
    """Address of the database owner. Alembic cannot run as fsp_app."""
    return settings.MIGRATE_DATABASE_URL or settings.DATABASE_URL
