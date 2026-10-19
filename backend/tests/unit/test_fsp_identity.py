"""FSP ID linking by OpenID Connect (code flow + PKCE) and the registry client of the proposed contract."""
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.core.config import settings
from app.services.fsp import identity
from app.services.fsp.registry import FSPRegistryError, HttpFSPAdapter, registry_id


class FakeRedis:
    def __init__(self):
        self.data = {}

    async def set(self, key, value, ex=None):
        self.data[key] = value

    async def getdel(self, key):
        return self.data.pop(key, None)


@pytest.fixture
def redis(monkeypatch):
    fake = FakeRedis()

    async def get():
        return fake
    monkeypatch.setattr(identity, "get_redis", get)
    return fake


def _query(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


# --- demo provider: the same protocol as Keycloak ----------------------------------------------------

async def test_demo_flow_links_the_fsp_id_confirmed_by_the_provider(redis):
    person = uuid.uuid4()
    provider = identity.MockFspIdProvider()
    started = await identity.start(person, provider)
    q = _query(started.authorize_url)
    assert started.authorize_url.startswith(identity.DEMO_AUTHORIZE_PATH)
    assert q["code_challenge_method"] == "S256" and q["response_type"] == "code" and "password" not in q
    code = await provider.issue_code(
        "FSP2005", q["client_id"], q["redirect_uri"], q["code_challenge"], nonce=q["nonce"])
    assert await identity.finish(person, code, q["state"], provider) == "FSP2005"


async def test_code_and_state_work_once(redis):
    person = uuid.uuid4()
    provider = identity.MockFspIdProvider()
    q = _query((await identity.start(person, provider)).authorize_url)
    code = await provider.issue_code(
        "FSP2005", q["client_id"], q["redirect_uri"], q["code_challenge"], nonce=q["nonce"])
    await identity.finish(person, code, q["state"], provider)
    with pytest.raises(identity.FspIdError):
        await identity.finish(person, code, q["state"], provider)


async def test_state_of_another_candidate_is_refused(redis):
    provider = identity.MockFspIdProvider()
    q = _query((await identity.start(uuid.uuid4(), provider)).authorize_url)
    code = await provider.issue_code("FSP2005", q["client_id"], q["redirect_uri"], q["code_challenge"])
    with pytest.raises(identity.FspIdError):
        await identity.finish(uuid.uuid4(), code, q["state"], provider)


async def test_code_bound_to_another_challenge_is_refused(redis):
    """PKCE: a code stolen from the redirect is useless without this session's verifier."""
    person = uuid.uuid4()
    provider = identity.MockFspIdProvider()
    q = _query((await identity.start(person, provider)).authorize_url)
    foreign = identity.pkce_challenge("someone-elses-verifier-" + "x" * 30)
    code = await provider.issue_code("FSP2005", q["client_id"], q["redirect_uri"], foreign)
    with pytest.raises(identity.FspIdError):
        await identity.finish(person, code, q["state"], provider)


async def test_unknown_client_or_redirect_gets_no_code(redis):
    provider = identity.MockFspIdProvider()
    with pytest.raises(identity.FspIdError):
        await provider.issue_code("FSP2005", "other-client", provider.redirect_uri(), "c" * 43)
    with pytest.raises(identity.FspIdError):
        await provider.issue_code("FSP2005", settings.FSP_ID_CLIENT_ID, "https://evil.example/cb", "c" * 43)


def test_pkce_challenge_matches_rfc7636_example():
    assert identity.pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == \
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


# --- Keycloak provider: the ID token is verified before the claim is read --------------------------------

ISSUER = "https://id.example.test/realms/fsp"


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    jwk_public = RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk_public.update(kid="k1", use="sig", alg="RS256")
    return pem, {"keys": [jwk_public]}


def _keycloak(monkeypatch, claims: dict, sign_with: str | None = None):
    pem, jwks = _keypair()
    token = jwt.encode(claims, sign_with or pem, algorithm="RS256", headers={"kid": "k1"})
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            seen["form"] = parse_qs(request.content.decode())
            return httpx.Response(200, json={"id_token": token, "access_token": "a", "token_type": "Bearer"})
        if request.url.path.endswith("/certs"):
            return httpx.Response(200, json=jwks)
        return httpx.Response(404)

    monkeypatch.setattr(settings, "FSP_ID_ISSUER", ISSUER)
    monkeypatch.setattr(settings, "FSP_ID_CLIENT_SECRET", "s3cret")
    provider = identity.KeycloakFspIdProvider(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return provider, seen


def _claims(**over):
    now = int(time.time())
    return {"iss": ISSUER, "aud": settings.FSP_ID_CLIENT_ID, "sub": "u1", "iat": now, "exp": now + 300,
            "fsp_id": "FSP4321", **over}


async def test_keycloak_exchange_reads_the_claim_of_a_valid_token(monkeypatch):
    provider, seen = _keycloak(monkeypatch, _claims())
    assert await provider.exchange("the-code", "the-verifier") == "FSP4321"
    assert seen["form"]["code_verifier"] == ["the-verifier"] and seen["form"]["client_secret"] == ["s3cret"]
    assert provider.authorize_url("st", "ch").startswith(f"{ISSUER}/protocol/openid-connect/auth?")


@pytest.mark.parametrize("bad", [{"aud": "another-client"}, {"iss": "https://evil.example/realms/fsp"},
                                 {"exp": int(time.time()) - 10}, {"fsp_id": None}])
async def test_keycloak_rejects_a_token_for_someone_else_or_expired(monkeypatch, bad):
    provider, _ = _keycloak(monkeypatch, _claims(**bad))
    with pytest.raises(identity.FspIdError):
        await provider.exchange("the-code", "the-verifier")


async def test_keycloak_rejects_a_token_signed_by_another_key(monkeypatch):
    other_pem, _ = _keypair()
    provider, _ = _keycloak(monkeypatch, _claims(), sign_with=other_pem)
    with pytest.raises(identity.FspIdError):
        await provider.exchange("the-code", "the-verifier")


async def test_nonce_binds_the_id_token_to_this_login_request(redis, monkeypatch):
    person = uuid.uuid4()
    provider, _ = _keycloak(monkeypatch, _claims(nonce="right-nonce"))
    url = provider.authorize_url("st", "ch", nonce="right-nonce")
    assert _query(url)["nonce"] == "right-nonce"
    assert await provider.exchange("the-code", "the-verifier", nonce="right-nonce") == "FSP4321"
    with pytest.raises(identity.FspIdError):
        await provider.exchange("the-code", "the-verifier", nonce="other-nonce")
    no_nonce, _ = _keycloak(monkeypatch, _claims())
    with pytest.raises(identity.FspIdError):
        await no_nonce.exchange("the-code", "the-verifier", nonce="right-nonce")
    demo = identity.MockFspIdProvider()
    started = await identity.start(person, demo)
    q = _query(started.authorize_url)
    assert len(q["nonce"]) >= 16
    wrong = await demo.issue_code("FSP2005", q["client_id"], q["redirect_uri"], q["code_challenge"], nonce="other")
    with pytest.raises(identity.FspIdError):
        await identity.finish(person, wrong, q["state"], demo)
    bare = await identity.start(person, demo)
    bq = _query(bare.authorize_url)
    omitted = await demo.issue_code("FSP2005", bq["client_id"], bq["redirect_uri"], bq["code_challenge"])
    with pytest.raises(identity.FspIdError):
        await identity.finish(person, omitted, bq["state"], demo)


# --- registry client of the proposed contract ------------------------------------------------------------

PAYLOAD = {"fsp_id": "FSP4321", "display_name": "Участник Тестовый", "region": "Томская область",
           "birth_date": "2002-03-04", "results": [
               {"event_id": "E1", "event_name": "Чемпионат России", "discipline": "algorithmic",
                "competition_status": "russia_championship", "place": 7, "total_participants": 150,
                "is_team": False, "team_size": 1, "event_date": "2025-11-20", "regions_count": 40},
               {"event_id": "E2", "event_name": "Неизвестная", "discipline": "chess",
                "competition_status": "other", "place": 1, "total_participants": 10, "event_date": "2025-01-01"},
           ]}


def _registry(monkeypatch, status: int, body: dict | None = None):
    monkeypatch.setattr(settings, "FSP_API_URL", "https://registry.example.test/v1")
    monkeypatch.setattr(settings, "FSP_API_KEY", "k")
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["path"] = request.url.path
        return httpx.Response(status, content=json.dumps(body or {}).encode())
    return HttpFSPAdapter(httpx.AsyncClient(transport=httpx.MockTransport(handler))), seen


async def test_registry_client_maps_the_contract_and_skips_unknown_disciplines(monkeypatch):
    adapter, seen = _registry(monkeypatch, 200, PAYLOAD)
    participant = await adapter.fetch_participant("FSP4321")
    assert seen == {"auth": "Bearer k", "path": "/v1/participants/FSP4321"}
    assert participant.fsp_id == "FSP4321" and [r.event_id for r in participant.results] == ["E1"]
    assert participant.gender is None


async def test_registry_client_does_not_request_an_id_outside_one_segment(monkeypatch):
    adapter, seen = _registry(monkeypatch, 200, PAYLOAD)
    with pytest.raises(FSPRegistryError):
        await adapter.fetch_participant("FSP1/other")
    assert seen == {}
    assert registry_id("FSP2000") == "FSP2000"
    assert registry_id("../x") is None
    assert registry_id(True) is None


async def test_registry_client_404_is_none_and_other_errors_raise(monkeypatch):
    adapter, _ = _registry(monkeypatch, 404)
    assert await adapter.fetch_participant("FSP0") is None
    adapter, _ = _registry(monkeypatch, 500)
    with pytest.raises(FSPRegistryError):
        await adapter.fetch_participant("FSP0")
    adapter, _ = _registry(monkeypatch, 200, {"fsp_id": "FSP0"})
    with pytest.raises(FSPRegistryError):
        await adapter.fetch_participant("FSP0")
