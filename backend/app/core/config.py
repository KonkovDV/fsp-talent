from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    SECRET_KEY: str = "change-me-32-chars-minimum-secret"
    DATABASE_URL: str = "postgresql+asyncpg://fsp:fsp@localhost:5432/fsp_talent"
    REDIS_URL: str = "redis://localhost:6379/0"
    DEBUG: bool = False
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
    ALGORITHM: str = "HS256"

    # GigaChat (AI advisor). Credentials = Authorization key from developers.sber.ru
    GIGACHAT_CREDENTIALS: str = ""
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"
    GIGACHAT_MODEL: str = "GigaChat-2-Pro"
    GIGACHAT_VERIFY_SSL: bool = True

    # Embeddings
    EMBEDDING_MODEL: str = "deepvk/USER-bge-m3"
    EMBEDDING_DIM: int = 1024

    # Verifiable Credentials (W3C VC 2.0, Data Integrity eddsa-jcs-2022)
    VC_PRIVATE_KEY_PATH: str = "/secrets/vc_ed25519.pem"

    # FSP API (real mode)
    FSP_API_URL: str = "https://api.fsp.ru/v1"
    FSP_API_KEY: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
