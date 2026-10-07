import os
import secrets
import time
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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
    DATABASE_URL: str = "postgresql+asyncpg://fsp:fsp@localhost:5432/fsp_talent"
    REDIS_URL: str = "redis://localhost:6379/0"
    DEBUG: bool = False
    # The six-item jury trial is offered only when this is on. The demo compose turns it on.
    DEMO_MODE: bool = False
    VERSION: str = "1.1.0"
    PUBLIC_BASE_URL: str = "http://localhost"
    CORS_ORIGINS: str = "http://localhost,http://localhost:5173"

    # Feature flags
    FSP_MODE: str = "mock"   # mock | real
    AI_ENABLED: bool = True
    EMBEDDINGS_MODE: str = "off"   # off | model (sentence-transformers, see [ai] extra)

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

    # Embeddings
    EMBEDDING_MODEL: str = "deepvk/USER-bge-m3"
    EMBEDDING_DIM: int = 1024

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

    # FSP registry API (FSP_MODE=real): the contract we propose is in docs/FSP_INTEGRATION.md
    FSP_API_URL: str = ""
    FSP_API_KEY: str = ""

    # FSP ID login (OpenID Connect, Keycloak-compatible). mock: demo provider page on this site.
    FSP_ID_MODE: str = "mock"   # mock | oidc
    FSP_ID_ISSUER: str = ""     # https://<keycloak>/realms/<realm>, the address the browser opens
    FSP_ID_BACKEND_ISSUER: str = ""  # same realm as seen from the API container; empty uses FSP_ID_ISSUER
    FSP_ID_CLIENT_ID: str = "fsp-talent"
    FSP_ID_CLIENT_SECRET: str = ""
    FSP_ID_CLAIM: str = "fsp_id"


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
