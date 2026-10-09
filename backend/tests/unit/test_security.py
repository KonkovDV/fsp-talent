import base64
import json
from datetime import date, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_token,
    decode_token,
    hash_password,
    password_matches,
    verify_password,
)
from app.models.participant import Participant
from app.services.profile import adult_cutoff, born_adult


def test_access_token_round_trip_and_refresh_is_rejected():
    token = create_access_token("person-1", "participant")
    payload = decode_token(token)
    assert payload["sub"] == "person-1" and payload["role"] == "participant"
    with pytest.raises(ValueError, match="Access token"):
        decode_token(create_refresh_token("person-1", "participant"))


def test_expired_and_tampered_tokens_are_rejected():
    expired = create_token({"sub": "person-1", "role": "participant", "type": "access"}, expire_minutes=-1)
    with pytest.raises(ValueError):
        decode_token(expired)
    raw = create_access_token("person-1", "employer")
    forged = jwt.encode({"sub": "person-1", "role": "employer", "type": "access"}, "other-secret", algorithm="HS256")
    with pytest.raises(ValueError):
        decode_token(forged)
    header, body, sig = raw.split(".")
    with pytest.raises(ValueError):
        decode_token(f"{header}.{body}.{'A' * len(sig)}")


def test_a_missing_password_hash_still_runs_bcrypt(monkeypatch):
    seen = []

    def fake(plain: str, hashed: str) -> bool:
        seen.append(hashed)
        return True

    monkeypatch.setattr("app.core.security.verify_password", fake)
    assert password_matches("demo12345", None) is False
    assert password_matches("demo12345", "") is False
    assert seen and all(item.startswith("$2b$") for item in seen)


def test_password_matches_the_stored_hash_only():
    stored = hash_password("demo12345")
    assert password_matches("demo12345", stored)
    assert not password_matches("wrong-pass", stored)


def test_bcrypt_does_not_store_the_password():
    first, second = hash_password("demo12345"), hash_password("demo12345")
    assert first != "demo12345" and first != second
    assert verify_password("demo12345", first)
    assert not verify_password("wrong-pass", first)
    assert not verify_password("x" * 80, first)


def test_discoverable_hides_minors_without_consent_and_hidden_profiles():
    assert Participant(is_visible=True, is_minor=False, minor_consent_given=False).discoverable
    assert Participant(is_visible=True, is_minor=True, minor_consent_given=True).discoverable
    assert not Participant(is_visible=True, is_minor=True, minor_consent_given=False).discoverable
    assert not Participant(is_visible=False, is_minor=False, minor_consent_given=False).discoverable


def test_unsigned_token_is_rejected():
    def segment(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    unsigned = f"{segment({'alg': 'none', 'typ': 'JWT'})}.{segment({'sub': 'person-1', 'type': 'access'})}."
    with pytest.raises(ValueError, match="Invalid token"):
        decode_token(unsigned)


def test_birth_date_not_the_stored_flag_decides_adulthood():
    assert adult_cutoff(date(2024, 2, 29)) == date(2006, 2, 28)
    assert not born_adult(date(2012, 5, 1), is_minor=False, today=date(2026, 10, 4))
    assert born_adult(date(2000, 1, 1), is_minor=True, today=date(2026, 10, 4))
    assert not born_adult(None, is_minor=True, today=date(2026, 10, 4))


def test_password_reset_epoch_rejects_the_old_token():
    from app.core.security import epochs_match
    assert epochs_match(0, 0)
    assert epochs_match(None, 0)
    assert not epochs_match(0, 1)


def test_the_browser_does_not_receive_the_refresh_token_in_the_body():
    from app.api.v1.auth import REFRESH_COOKIE, TokenOut, browser_tokens, presented_refresh

    issued = TokenOut(access_token="access", refresh_token="refresh-secret", role="participant")
    shown = browser_tokens(issued)
    assert shown.refresh_token == "" and issued.refresh_token == "refresh-secret"
    assert REFRESH_COOKIE == "fsp_refresh"
    assert presented_refresh(None, "from-cookie") == "from-cookie"
    assert presented_refresh("from-body", "from-cookie") == "from-body"
    assert presented_refresh("  ", None) is None


def test_client_ip_trusts_x_real_ip():
    from starlette.requests import Request

    from app.api.v1.auth import _client_ip

    request = Request({
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": "/", "raw_path": b"/", "query_string": b"",
        "headers": [(b"x-real-ip", b"203.0.113.10"), (b"x-forwarded-for", b"198.51.100.1")],
        "client": ("10.0.0.8", 1), "server": ("test", 80),
    })
    assert _client_ip(request) == "203.0.113.10"
    from app.services.identity import client_fingerprint
    forwarded_only = Request({
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": "/", "raw_path": b"/", "query_string": b"",
        "headers": [(b"x-forwarded-for", b"198.51.100.1")],
        "client": ("10.0.0.8", 1), "server": ("test", 80),
    })
    assert client_fingerprint(forwarded_only)[0] == client_fingerprint(Request({
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": "/", "raw_path": b"/", "query_string": b"", "headers": [],
        "client": ("10.0.0.8", 1), "server": ("test", 80),
    }))[0]


def test_a_429_without_its_own_header_still_says_retry_after():
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.api.errors import install_error_handlers

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/limited")
    def limited():
        raise HTTPException(429, "подождите")

    response = TestClient(app).get("/limited")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


async def test_an_old_refresh_burns_the_current_generation():
    from types import SimpleNamespace

    from fastapi import Response
    from starlette.requests import Request

    from app.api.errors import ApiError
    from app.api.v1.auth import refresh
    from app.core.security import create_refresh_token

    person = "11111111-1111-1111-1111-111111111111"
    account = SimpleNamespace(id=person, token_epoch=0, refresh_nonce=2, deleted_at=None)
    committed = []

    class Db:
        async def get(self, _model, _id, with_for_update=False):
            return account

        async def commit(self):
            committed.append(account.token_epoch)

    old = create_refresh_token(person, "participant", epoch=0, nonce=0)
    request = Request({
        "type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
        "path": "/api/v1/auth/refresh", "raw_path": b"/api/v1/auth/refresh", "query_string": b"",
        "headers": [], "client": ("127.0.0.1", 1), "server": ("test", 80),
    })
    with pytest.raises(ApiError):
        await refresh(Response(), request, body=type("B", (), {"refresh_token": old})(), db=Db())
    assert account.token_epoch == 1 and committed == [1]
    current = create_refresh_token(person, "participant", epoch=0, nonce=2)
    with pytest.raises(ApiError):
        await refresh(Response(), request, body=type("B", (), {"refresh_token": current})(), db=Db())


async def test_the_previous_refresh_inside_the_grace_window_does_not_burn(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from fastapi import Response
    from starlette.requests import Request

    from app.api.errors import ApiError
    from app.api.v1.auth import refresh
    from app.core.security import create_refresh_token

    person = "11111111-1111-1111-1111-111111111111"
    account = SimpleNamespace(id=person, token_epoch=0, refresh_nonce=2, deleted_at=None)

    class Db:
        async def get(self, _model, _id, with_for_update=False):
            return account

        async def commit(self):
            raise AssertionError("grace must not commit")

    monkeypatch.setattr("app.api.v1.auth.refresh_grace_open", AsyncMock(return_value=True))
    previous = create_refresh_token(person, "participant", epoch=0, nonce=1)
    request = Request({
        "type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
        "path": "/api/v1/auth/refresh", "raw_path": b"/api/v1/auth/refresh", "query_string": b"",
        "headers": [], "client": ("127.0.0.1", 1), "server": ("test", 80),
    })
    with pytest.raises(ApiError) as caught:
        await refresh(Response(), request, body=type("B", (), {"refresh_token": previous})(), db=Db())
    assert caught.value.code == "refresh_superseded"
    assert account.token_epoch == 0


def test_refresh_rotation_kills_the_presented_token():
    from app.core.security import decode_refresh_token, next_refresh_nonce

    assert next_refresh_nonce(None, 0) == 1
    assert next_refresh_nonce(None, 1) is None
    assert next_refresh_nonce(0, 0) == 1
    assert next_refresh_nonce(0, 1) is None
    assert next_refresh_nonce(2, 2) == 3
    issued = create_refresh_token("person-1", "participant", epoch=4, nonce=2)
    assert decode_refresh_token(issued)["rn"] == 2
    assert decode_refresh_token(issued)["ep"] == 4


def test_refresh_stops_when_the_account_is_gone():
    from types import SimpleNamespace

    from app.api.v1.auth import account_can_refresh

    live = SimpleNamespace(deleted_at=None)
    gone = SimpleNamespace(deleted_at=date(2026, 10, 1))
    assert account_can_refresh(live)
    assert not account_can_refresh(gone)
    assert not account_can_refresh(None)


async def test_erasure_invalidates_tokens_and_hides_the_card():
    import uuid

    from app.services.privacy import erase_participant

    class Db:
        def add(self, _obj):
            return None

        async def execute(self, *_args, **_kwargs):
            return None

        async def flush(self):
            return None

    person = Participant(id=uuid.uuid4(), token_epoch=2, display_name="Анна", email="a@example.test",
                         is_visible=True, guardian_email="parent@example.test")
    await erase_participant(Db(), person, "account_deleted")
    assert person.token_epoch == 3
    assert person.deleted_at is not None
    assert person.display_name is None and person.email is None
    assert person.guardian_email is None and person.guardian_consent_at is None
    assert person.discoverable is False


def test_offer_terms_stay_immutable_and_one_pending_pair_is_unique():
    from pathlib import Path

    from app.api.v1.offers import router

    methods: set[str] = set()
    for route in router.routes:
        methods |= set(getattr(route, "methods", ()))
    assert "PUT" not in methods and "PATCH" not in methods
    migration = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0001_initial.py"
    assert "uq_offers_pending_pair" in migration.read_text(encoding="utf-8")


def test_app_connections_leave_the_superuser_role(monkeypatch):
    import asyncio
    from pathlib import Path

    from app.core import app_login
    from app.core.config import migration_database_url, settings

    root = Path(__file__).resolve().parents[3]
    backend = Path(__file__).resolve().parents[2]
    migration = (backend / "alembic" / "versions" / "0001_initial.py").read_text(encoding="utf-8")
    assert "CREATE ROLE fsp_app NOLOGIN NOSUPERUSER NOBYPASSRLS" in migration
    assert "SET SESSION AUTHORIZATION fsp_app" in (backend / "app" / "core" / "database.py").read_text(encoding="utf-8")
    compose = (root / "deploy" / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert compose.count("postgresql+asyncpg://fsp_app:${APP_DB_PASSWORD:?}@postgres:5432/fsp_talent") == 3
    assert compose.count("postgresql+asyncpg://fsp:${POSTGRES_PASSWORD:?}@postgres:5432/fsp_talent") == 1
    assert "python -m app.core.app_login" in (backend / "Dockerfile").read_text(encoding="utf-8")
    monkeypatch.setattr(settings, "MIGRATE_DATABASE_URL", "postgresql+asyncpg://fsp:owner@db/fsp_talent")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://fsp_app:app@db/fsp_talent")
    assert migration_database_url() == "postgresql+asyncpg://fsp:owner@db/fsp_talent"
    assert app_login.login_statement("ab" * 16).endswith("'" + ("ab" * 16) + "'")
    monkeypatch.delenv("APP_DB_PASSWORD", raising=False)
    asyncio.run(app_login.enable())
    monkeypatch.setenv("APP_DB_PASSWORD", "cd" * 16)
    monkeypatch.setenv("MIGRATE_DATABASE_URL", "postgresql+asyncpg://fsp:owner@db/fsp_talent")
    done = {}

    class Conn:
        async def execute(self, statement):
            done["sql"] = statement

        async def close(self):
            done["closed"] = True

    async def connect(url):
        done["url"] = url
        return Conn()

    monkeypatch.setitem(__import__("sys").modules, "asyncpg", type("M", (), {"connect": staticmethod(connect)}))
    asyncio.run(app_login.enable())
    assert done["url"] == "postgresql://fsp:owner@db/fsp_talent"
    assert done["closed"] is True


def test_settings_secret_is_the_signing_key():
    token = create_access_token("person-1", "participant")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["type"] == "access"
    assert timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds() > 0


def _request(path: str, token: str | None = None):
    from starlette.requests import Request

    headers = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return Request({
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": b"", "headers": headers,
        "client": ("127.0.0.1", 9), "server": ("test", 80),
    })


def test_export_keeps_the_participant_scope():
    from app.core.rls import current, reset_rls
    from app.main import _rls_token

    token = create_access_token("person-1", "participant")
    ctx = _rls_token(_request("/api/v1/auth/me/export", token))
    try:
        scope = current()
        assert scope["bypass"] is False
        assert scope["participant_id"] == "person-1"
    finally:
        reset_rls(ctx)


def test_a_login_path_without_a_token_bypasses_and_a_future_auth_path_does_not():
    from app.core.rls import current, reset_rls
    from app.main import _rls_token

    login = _rls_token(_request("/api/v1/auth/participant/token"))
    try:
        assert current()["bypass"] is True
    finally:
        reset_rls(login)
    future = _rls_token(_request("/api/v1/auth/me/export"))
    try:
        assert current()["bypass"] is False
        assert current()["participant_id"] == ""
    finally:
        reset_rls(future)
