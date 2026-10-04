from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.participant import Participant


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


def test_settings_secret_is_the_signing_key():
    token = create_access_token("person-1", "participant")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["type"] == "access"
    assert timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds() > 0
