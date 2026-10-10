"""A taken address answers like a new registration. The letter goes to that mailbox."""
from types import SimpleNamespace

from app.api.v1 import auth


async def test_a_taken_email_answers_like_a_new_registration(monkeypatch):
    sent = []

    async def quiet(*_args, **_kwargs):
        return None

    async def remember(email, role):
        sent.append((email, role))

    async def account(_db, _role, _email):
        return SimpleNamespace(email_verified_at=object())

    monkeypatch.setattr(auth, "check_required_consents", lambda *_a, **_k: None)
    monkeypatch.setattr(auth, "_charge_registration", quiet)
    monkeypatch.setattr(auth, "_account", account)
    monkeypatch.setattr("app.services.identity.send_already_registered", remember)
    body = auth.ParticipantRegister(
        email="taken@example.com", password="password12", is_adult=True, consents=["pd_candidate", "terms"])
    taken = await auth.register_participant(body, SimpleNamespace(), None)
    quiet_shape = auth.VerificationSent(
        email="taken@example.com", role="participant", expires_in_minutes=taken.expires_in_minutes)
    assert taken.status == "verification_sent" and taken.demo_code is None
    assert sent == [("taken@example.com", "participant")]
    assert set(taken.model_dump()) == set(quiet_shape.model_dump())
