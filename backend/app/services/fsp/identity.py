"""FSP ID: linking a platform account to an FSP participant through OpenID Connect (TZ 2, TZ 3.5).

The case says FSP ID will run on Keycloak. The platform is an ordinary confidential OIDC client:
authorization code flow with PKCE (S256), the candidate types the FSP password only on the provider's page,
and the platform receives a signed ID token with the participant's FSP ID in a claim.

Two providers implement the same two calls:

- MockFspIdProvider (FSP_ID_MODE=mock, the demo): the provider's login page is a page of this site marked
  "демо-провайдер"; it checks the demo registry (FSP2000–FSP2099, password "test") and issues a one-time code.
- KeycloakFspIdProvider (FSP_ID_MODE=oidc): a Keycloak realm or any OIDC provider. Endpoints follow Keycloak
  paths under FSP_ID_ISSUER; the ID token is verified against the realm's JWKS (signature, issuer, audience,
  expiry) before the claim FSP_ID_CLAIM is read.

State, PKCE verifier and demo codes live in Redis with short TTLs and are deleted on first use.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
from jose import jwt

from app.core.config import settings
from app.core.redis_client import get_redis

STATE_TTL_S = 600
CODE_TTL_S = 120
CALLBACK_PATH = "/candidate/fsp-callback"
DEMO_AUTHORIZE_PATH = "/fsp-id/authorize"


class FspIdError(Exception):
    """The provider refused the code or returned a token we cannot trust."""


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


@dataclass
class Started:
    authorize_url: str
    state: str


class FspIdProvider(Protocol):
    name: str

    def redirect_uri(self) -> str: ...
    def authorize_url(self, state: str, challenge: str) -> str: ...
    async def exchange(self, code: str, verifier: str) -> str: ...


async def _put(key: str, value: dict, ttl: int) -> None:
    redis = await get_redis()
    await redis.set(key, json.dumps(value), ex=ttl)


async def _take(key: str) -> dict | None:
    redis = await get_redis()
    raw = await redis.getdel(key)
    return json.loads(raw) if raw else None


class MockFspIdProvider:
    """Demo provider: same protocol as Keycloak, the login page is ours and says so."""

    name = "mock"

    def redirect_uri(self) -> str:
        return CALLBACK_PATH

    def authorize_url(self, state: str, challenge: str) -> str:
        query = urlencode({
            "response_type": "code", "client_id": settings.FSP_ID_CLIENT_ID, "scope": "openid",
            "redirect_uri": self.redirect_uri(), "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
        })
        return f"{DEMO_AUTHORIZE_PATH}?{query}"

    async def issue_code(self, fsp_id: str, client_id: str, redirect_uri: str, challenge: str) -> str:
        """What the provider does after a successful login: a one-time code bound to the PKCE challenge."""
        if client_id != settings.FSP_ID_CLIENT_ID or redirect_uri != self.redirect_uri():
            raise FspIdError("client")
        code = secrets.token_urlsafe(24)
        await _put(f"fspid:code:{code}", {"fsp_id": fsp_id, "challenge": challenge,
                                          "redirect_uri": redirect_uri}, CODE_TTL_S)
        return code

    async def exchange(self, code: str, verifier: str) -> str:
        grant = await _take(f"fspid:code:{code}")
        if grant is None or grant["redirect_uri"] != self.redirect_uri():
            raise FspIdError("code")
        if not secrets.compare_digest(grant["challenge"], pkce_challenge(verifier)):
            raise FspIdError("pkce")
        return grant["fsp_id"]


class KeycloakFspIdProvider:
    """OIDC client for a Keycloak realm (FSP_ID_ISSUER = https://<host>/realms/<realm>)."""

    name = "oidc"

    def __init__(self, http: httpx.AsyncClient | None = None):
        self._http = http
        self.issuer = settings.FSP_ID_ISSUER.rstrip("/")

    def redirect_uri(self) -> str:
        return settings.PUBLIC_BASE_URL.rstrip("/") + CALLBACK_PATH

    def authorize_url(self, state: str, challenge: str) -> str:
        query = urlencode({
            "response_type": "code", "client_id": settings.FSP_ID_CLIENT_ID, "scope": "openid",
            "redirect_uri": self.redirect_uri(), "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
        })
        return f"{self.issuer}/protocol/openid-connect/auth?{query}"

    async def _client(self) -> httpx.AsyncClient:
        return self._http or httpx.AsyncClient(timeout=10)

    async def exchange(self, code: str, verifier: str) -> str:
        client = await self._client()
        try:
            token = await client.post(f"{self.issuer}/protocol/openid-connect/token", data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri(),
                "client_id": settings.FSP_ID_CLIENT_ID, "client_secret": settings.FSP_ID_CLIENT_SECRET,
                "code_verifier": verifier,
            })
            if token.status_code != 200 or "id_token" not in token.json():
                raise FspIdError("token")
            keys = await client.get(f"{self.issuer}/protocol/openid-connect/certs")
            keys.raise_for_status()
            jwks = keys.json()
        except (httpx.HTTPError, ValueError) as e:
            raise FspIdError("provider") from e
        finally:
            if self._http is None:
                await client.aclose()
        try:
            claims = jwt.decode(token.json()["id_token"], jwks, algorithms=["RS256", "ES256"],
                                audience=settings.FSP_ID_CLIENT_ID, issuer=self.issuer,
                                options={"verify_at_hash": False})
        except Exception as e:   # jose raises several error types; all mean "do not trust this token"
            raise FspIdError("id_token") from e
        fsp_id = claims.get(settings.FSP_ID_CLAIM)
        if not isinstance(fsp_id, str) or not fsp_id:
            raise FspIdError("claim")
        return fsp_id


def get_fsp_id_provider() -> MockFspIdProvider | KeycloakFspIdProvider:
    return KeycloakFspIdProvider() if settings.FSP_ID_MODE == "oidc" else MockFspIdProvider()


async def start(participant_id: uuid.UUID, provider: FspIdProvider | None = None) -> Started:
    """Create state and the PKCE verifier on the server, bound to the signed-in candidate."""
    provider = provider or get_fsp_id_provider()
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    await _put(f"fspid:state:{state}", {"participant_id": str(participant_id), "verifier": verifier}, STATE_TTL_S)
    return Started(provider.authorize_url(state, pkce_challenge(verifier)), state)


async def finish(participant_id: uuid.UUID, code: str, state: str, provider: FspIdProvider | None = None) -> str:
    """Return the FSP ID confirmed by the provider. A state is single-use and belongs to one candidate."""
    provider = provider or get_fsp_id_provider()
    saved = await _take(f"fspid:state:{state}")
    if saved is None or saved["participant_id"] != str(participant_id):
        raise FspIdError("state")
    return await provider.exchange(code, saved["verifier"])
