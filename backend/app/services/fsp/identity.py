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
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import settings
from app.core.redis_client import get_redis

STATE_TTL_S = 600
CODE_TTL_S = 120
CALLBACK_PATH = "/candidate/fsp-callback"
# Sign-in by FSP ID (no platform session yet) returns to its own page, registered with the provider apart
# from the linking address: a code issued for one flow is refused by the other.
SIGNIN_CALLBACK_PATH = "/auth/fsp-callback"
TICKET_TTL_S = 900
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
    binder: str = ""  # sign-in only: the browser must send this cookie back


class FspIdProvider(Protocol):
    name: str

    def redirect_uri(self, path: str = CALLBACK_PATH) -> str: ...
    def authorize_url(self, state: str, challenge: str, path: str = CALLBACK_PATH) -> str: ...
    async def exchange(self, code: str, verifier: str, path: str = CALLBACK_PATH) -> str: ...


async def _put(key: str, value: dict, ttl: int) -> None:
    redis = await get_redis()
    await redis.set(key, json.dumps(value), ex=ttl)


async def _peek(key: str) -> dict | None:
    redis = await get_redis()
    raw = await redis.get(key)
    return json.loads(raw) if raw else None


async def _take(key: str) -> dict | None:
    redis = await get_redis()
    raw = await redis.getdel(key)
    return json.loads(raw) if raw else None


def _binder_matches(saved: dict, binder: str | None) -> bool:
    expected = saved.get("binder_sha256")
    if not isinstance(expected, str) or not binder:
        return False
    actual = hashlib.sha256(binder.encode()).hexdigest()
    return hmac.compare_digest(expected, actual)


class MockFspIdProvider:
    """Demo provider: same protocol as Keycloak, the login page is ours and says so."""

    name = "mock"
    # The addresses registered for this client, as in the client settings of a Keycloak realm.
    ALLOWED_REDIRECTS = (CALLBACK_PATH, SIGNIN_CALLBACK_PATH)

    def redirect_uri(self, path: str = CALLBACK_PATH) -> str:
        return path

    def authorize_url(self, state: str, challenge: str, path: str = CALLBACK_PATH) -> str:
        query = urlencode({
            "response_type": "code", "client_id": settings.FSP_ID_CLIENT_ID, "scope": "openid",
            "redirect_uri": self.redirect_uri(path), "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
        })
        return f"{DEMO_AUTHORIZE_PATH}?{query}"

    async def issue_code(self, fsp_id: str, client_id: str, redirect_uri: str, challenge: str) -> str:
        """What the provider does after a successful login: a one-time code bound to the PKCE challenge."""
        if client_id != settings.FSP_ID_CLIENT_ID or redirect_uri not in self.ALLOWED_REDIRECTS:
            raise FspIdError("client")
        code = secrets.token_urlsafe(24)
        await _put(f"fspid:code:{code}", {"fsp_id": fsp_id, "challenge": challenge,
                                          "redirect_uri": redirect_uri}, CODE_TTL_S)
        return code

    async def exchange(self, code: str, verifier: str, path: str = CALLBACK_PATH) -> str:
        grant = await _take(f"fspid:code:{code}")
        if grant is None or grant["redirect_uri"] != self.redirect_uri(path):
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
        # The browser follows FSP_ID_ISSUER. The API fetches tokens from the in-network address
        # when the public host is not reachable from the container.
        self.backend = (settings.FSP_ID_BACKEND_ISSUER or settings.FSP_ID_ISSUER).rstrip("/")

    def redirect_uri(self, path: str = CALLBACK_PATH) -> str:
        return settings.PUBLIC_BASE_URL.rstrip("/") + path

    def authorize_url(self, state: str, challenge: str, path: str = CALLBACK_PATH) -> str:
        query = urlencode({
            "response_type": "code", "client_id": settings.FSP_ID_CLIENT_ID, "scope": "openid",
            "redirect_uri": self.redirect_uri(path), "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
        })
        return f"{self.issuer}/protocol/openid-connect/auth?{query}"

    async def _client(self) -> httpx.AsyncClient:
        return self._http or httpx.AsyncClient(timeout=10)

    async def exchange(self, code: str, verifier: str, path: str = CALLBACK_PATH) -> str:
        client = await self._client()
        try:
            token = await client.post(f"{self.backend}/protocol/openid-connect/token", data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri(path),
                "client_id": settings.FSP_ID_CLIENT_ID, "client_secret": settings.FSP_ID_CLIENT_SECRET,
                "code_verifier": verifier,
            })
            if token.status_code != 200 or "id_token" not in token.json():
                raise FspIdError("token")
            keys = await client.get(f"{self.backend}/protocol/openid-connect/certs")
            keys.raise_for_status()
            jwks = keys.json()
        except (httpx.HTTPError, ValueError) as e:
            raise FspIdError("provider") from e
        finally:
            if self._http is None:
                await client.aclose()
        try:
            id_token = token.json()["id_token"]
            kid = jwt.get_unverified_header(id_token).get("kid")
            keyset = jwt.PyJWKSet.from_dict(jwks)
            signing = next(k for k in keyset.keys if kid is None or k.key_id == kid)
            claims = jwt.decode(id_token, signing.key, algorithms=["RS256", "ES256"],
                                audience=settings.FSP_ID_CLIENT_ID, issuer=self.issuer)
        except Exception as e:   # a bad signature, key, audience or issuer all mean "do not trust this token"
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
    if saved is None or saved.get("participant_id") != str(participant_id):
        raise FspIdError("state")
    return await provider.exchange(code, saved["verifier"])


# --- sign-in by FSP ID (the single entry point of the Federation) ---------------------------------------

async def start_signin(provider: FspIdProvider | None = None) -> Started:
    """Same code flow with PKCE, but the state belongs to no account: the person is not signed in yet."""
    provider = provider or get_fsp_id_provider()
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    binder = secrets.token_urlsafe(32)
    digest = hashlib.sha256(binder.encode()).hexdigest()
    await _put(f"fspid:state:{state}",
               {"purpose": "signin", "verifier": verifier, "binder_sha256": digest}, STATE_TTL_S)
    return Started(provider.authorize_url(state, pkce_challenge(verifier), SIGNIN_CALLBACK_PATH), state, binder)


async def finish_signin(code: str, state: str, provider: FspIdProvider | None = None,
                        binder: str | None = None) -> str:
    """The FSP ID confirmed by the provider. The browser that started the login must present the cookie.

    A wrong cookie does not burn the state, so the real browser can still finish. A linking state is refused.
    """
    provider = provider or get_fsp_id_provider()
    key = f"fspid:state:{state}"
    saved = await _peek(key)
    if saved is None or saved.get("purpose") != "signin" or not _binder_matches(saved, binder):
        raise FspIdError("state")
    saved = await _take(key)
    if saved is None or not _binder_matches(saved, binder):
        raise FspIdError("state")
    return await provider.exchange(code, saved["verifier"], SIGNIN_CALLBACK_PATH)


async def issue_ticket(fsp_id: str) -> str:
    """A new person confirmed by FSP ID has no account yet. The account is created only after the consents
    (152-FZ), so the confirmed FSP ID waits for them under a one-time ticket that only the server can read."""
    ticket = secrets.token_urlsafe(32)
    await _put(f"fspid:ticket:{ticket}", {"fsp_id": fsp_id}, TICKET_TTL_S)
    return ticket


async def take_ticket(ticket: str) -> str:
    saved = await _take(f"fspid:ticket:{ticket}")
    if saved is None:
        raise FspIdError("ticket")
    return saved["fsp_id"]
