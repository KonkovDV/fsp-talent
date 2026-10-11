"""ST-OAS-04: a valid session of the other role gets 403 forbidden; a bad or missing session stays 401."""
import pytest
from fastapi import HTTPException

from app.api import deps


@pytest.fixture
def signed(monkeypatch):
    async def ok(db, payload):
        return object()
    monkeypatch.setattr(deps, "_open_account", ok)

    def use(role):
        payload = {"sub": "6f1c1a52-9d1e-4a39-9c39-3a1d2b0c0a11", "role": role}
        monkeypatch.setattr(deps, "decode_token", lambda t: payload)
    return use


@pytest.mark.parametrize("dep,other", [(deps.get_current_employer, "participant"),
                                       (deps.get_current_participant, "employer")])
async def test_other_role_is_403(signed, dep, other):
    signed(other)
    with pytest.raises(HTTPException) as caught:
        await dep("t", None)
    assert caught.value.status_code == 403


@pytest.mark.parametrize("dep,own", [(deps.get_current_employer, "employer"),
                                     (deps.get_current_participant, "participant")])
async def test_own_role_passes(signed, dep, own):
    signed(own)
    assert (await dep("t", None))["role"] == own


async def test_a_broken_token_is_still_401(monkeypatch):
    def bad(token):
        raise ValueError("Invalid token")
    monkeypatch.setattr(deps, "decode_token", bad)
    for dep in (deps.get_current_employer, deps.get_current_participant):
        with pytest.raises(HTTPException) as caught:
            await dep("t", None)
        assert caught.value.status_code == 401
