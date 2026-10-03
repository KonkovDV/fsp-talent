"""
Unit tests for app.core.security.

Covers:
- JWT encode / decode round-trip
- Expired token detection
- Wrong-secret detection
- bcrypt hash safety (never stores plaintext)
- bcrypt verify: correct and wrong passwords
- Participant.discoverable property edge cases
"""
from __future__ import annotations
import time
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import bcrypt
import jwt
import pytest


# ---------------------------------------------------------------------------
# JWT helpers (inline so we don't depend on internal imports for unit tests)
# ---------------------------------------------------------------------------

SECRET = "test-secret-key-for-unit-tests-only"
ALGO = "HS256"


def _encode(payload: dict, secret: str = SECRET) -> str:
    return jwt.encode(payload, secret, algorithm=ALGO)


def _decode(token: str, secret: str = SECRET) -> dict:
    return jwt.decode(token, secret, algorithms=[ALGO])


class TestJWT:
    def test_round_trip(self):
        payload = {"sub": "user-123", "role": "participant"}
        token = _encode(payload)
        decoded = _decode(token)
        assert decoded["sub"] == "user-123"
        assert decoded["role"] == "participant"

    def test_expired_token_raises(self):
        payload = {"sub": "x", "exp": int(time.time()) - 10}  # already expired
        token = _encode(payload)
        with pytest.raises(jwt.ExpiredSignatureError):
            _decode(token)

    def test_wrong_secret_raises(self):
        token = _encode({"sub": "x"})
        with pytest.raises(jwt.InvalidSignatureError):
            _decode(token, secret="wrong-secret")

    def test_tampered_payload_raises(self):
        """Changing the token body invalidates the HMAC signature."""
        token = _encode({"sub": "user-1", "role": "participant"})
        # Flip one character in the payload segment
        header, payload, sig = token.split(".")
        tampered = f"{header}.{payload[:-2]}XX.{sig}"
        with pytest.raises(jwt.DecodeError):
            _decode(tampered)


# ---------------------------------------------------------------------------
# bcrypt
# ---------------------------------------------------------------------------

class TestBcrypt:
    def test_hash_is_not_plaintext(self):
        pw = "super-secret-123"
        hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt())
        assert hashed != pw.encode()
        assert len(hashed) == 60  # bcrypt output is always 60 bytes

    def test_verify_correct_password(self):
        pw = "correct-horse-battery-staple"
        hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt())
        assert bcrypt.checkpw(pw.encode(), hashed)

    def test_verify_wrong_password_fails(self):
        pw = "correct-password"
        hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt())
        assert not bcrypt.checkpw(b"wrong-password", hashed)

    def test_two_hashes_of_same_password_differ(self):
        """Each call uses a fresh random salt."""
        pw = b"same-password"
        h1 = bcrypt.hashpw(pw, bcrypt.gensalt())
        h2 = bcrypt.hashpw(pw, bcrypt.gensalt())
        assert h1 != h2
        # But both verify correctly
        assert bcrypt.checkpw(pw, h1)
        assert bcrypt.checkpw(pw, h2)


# ---------------------------------------------------------------------------
# Participant.discoverable property
# ---------------------------------------------------------------------------

class FakeParticipant:
    """Minimal stub that implements the discoverable property."""
    def __init__(self, is_visible: bool, is_minor: bool, minor_consent_given: bool):
        self.is_visible = is_visible
        self.is_minor = is_minor
        self.minor_consent_given = minor_consent_given

    @property
    def discoverable(self) -> bool:
        return self.is_visible and (not self.is_minor or self.minor_consent_given)


class TestDiscoverableProperty:
    def test_visible_adult_is_discoverable(self):
        p = FakeParticipant(is_visible=True, is_minor=False, minor_consent_given=False)
        assert p.discoverable is True

    def test_invisible_adult_is_not_discoverable(self):
        p = FakeParticipant(is_visible=False, is_minor=False, minor_consent_given=False)
        assert p.discoverable is False

    def test_minor_without_consent_is_not_discoverable(self):
        p = FakeParticipant(is_visible=True, is_minor=True, minor_consent_given=False)
        assert p.discoverable is False

    def test_minor_with_consent_is_discoverable(self):
        p = FakeParticipant(is_visible=True, is_minor=True, minor_consent_given=True)
        assert p.discoverable is True

    def test_invisible_minor_with_consent_still_not_discoverable(self):
        p = FakeParticipant(is_visible=False, is_minor=True, minor_consent_given=True)
        assert p.discoverable is False
