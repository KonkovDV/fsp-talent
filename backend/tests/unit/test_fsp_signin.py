"""Sign-in by FSP ID: the Federation's single entry point (client Q&A), next to email registration."""
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import Response

from app.api.errors import ApiError
from app.api.v1 import auth
from app.core.security import decode_token
from app.models import Participant
from app.services.fsp import identity


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


class FakeDb:
    """Enough of AsyncSession for the callback: one lookup by FSP ID."""

    def __init__(self, account=None):
        self.account = account

    async def scalar(self, _query):
        return self.account


def _query(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


async def _code_for(fsp_id: str, provider=None):
    provider = provider or identity.MockFspIdProvider()
    q = _query((await identity.start_signin(provider)).authorize_url)
    code = await provider.issue_code(fsp_id, q["client_id"], q["redirect_uri"], q["code_challenge"])
    return q, code


async def test_signin_returns_to_its_own_registered_address(redis):
    q, _ = await _code_for("FSP2005")
    assert q["redirect_uri"] == identity.SIGNIN_CALLBACK_PATH != identity.CALLBACK_PATH
    assert identity.SIGNIN_CALLBACK_PATH in identity.MockFspIdProvider.ALLOWED_REDIRECTS
    with pytest.raises(identity.FspIdError):
        await identity.MockFspIdProvider().issue_code("FSP2005", q["client_id"], "/evil", q["code_challenge"])


async def test_signin_state_is_single_use(redis):
    q, code = await _code_for("FSP2005")
    assert await identity.finish_signin(code, q["state"]) == "FSP2005"
    with pytest.raises(identity.FspIdError):
        await identity.finish_signin(code, q["state"])


async def test_linking_and_signin_states_do_not_mix(redis):
    provider = identity.MockFspIdProvider()
    person = uuid.uuid4()
    link = _query((await identity.start(person, provider)).authorize_url)
    code = await provider.issue_code("FSP2005", link["client_id"], link["redirect_uri"], link["code_challenge"])
    with pytest.raises(identity.FspIdError):
        await identity.finish_signin(code, link["state"], provider)
    q, code = await _code_for("FSP2006", provider)
    with pytest.raises(identity.FspIdError):
        await identity.finish(person, code, q["state"], provider)


async def test_code_issued_for_linking_is_refused_at_signin(redis):
    """The code is bound to its redirect address, as an OIDC provider binds it."""
    provider = identity.MockFspIdProvider()
    q = _query((await identity.start_signin(provider)).authorize_url)
    code = await provider.issue_code("FSP2005", q["client_id"], identity.CALLBACK_PATH, q["code_challenge"])
    with pytest.raises(identity.FspIdError):
        await identity.finish_signin(code, q["state"], provider)


async def test_existing_linked_account_signs_in(redis):
    q, code = await _code_for("FSP2005")
    account = Participant(id=uuid.uuid4(), fsp_id="FSP2005")
    out = await auth.fsp_signin_callback(auth.FspSignInCallback(code=code, state=q["state"]),
                                         response=Response(), db=FakeDb(account))
    assert out["status"] == "signed_in"
    payload = decode_token(out["access_token"])
    assert payload["sub"] == str(account.id) and payload["role"] == "participant"


async def test_new_person_must_accept_consents_before_an_account_exists(redis, monkeypatch):
    q, code = await _code_for("FSP2007")
    out = await auth.fsp_signin_callback(auth.FspSignInCallback(code=code, state=q["state"]),
                                         response=Response(), db=FakeDb(None))
    assert out["status"] == "needs_consent" and "access_token" not in out
    ticket = out["ticket"]
    # Without the required consents nothing is created, and the ticket is not spent.
    with pytest.raises(ApiError) as err:
        await auth.fsp_signin_signup(auth.FspSignUpIn(ticket=ticket, consents=["terms"]),
                                     request=None, response=Response(), db=None)
    assert err.value.code == "consent_required"
    assert f"fspid:ticket:{ticket}" in redis.data
    assert await identity.take_ticket(ticket) == "FSP2007"


async def test_ticket_is_single_use(redis):
    ticket = await identity.issue_ticket("FSP2008")
    assert await identity.take_ticket(ticket) == "FSP2008"
    with pytest.raises(identity.FspIdError):
        await identity.take_ticket(ticket)
    with pytest.raises(ApiError) as err:
        await auth.fsp_signin_signup(auth.FspSignUpIn(ticket=ticket, consents=["terms", "pd_candidate"]),
                                     request=None, response=Response(), db=None)
    assert err.value.code == "fsp_ticket_invalid"
