"""LEG-06: a birth date given at signup is stored and must agree with the 18+ tick."""
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.errors import ApiError
from app.api.v1 import auth
from app.models import Participant
from tests.integration.conftest import stamp, wipe_people


@pytest.fixture
def quiet(monkeypatch):
    async def nothing(*a, **k):
        return None
    async def sent(db, role, p, email):
        return auth.VerificationSent(email=email, role=role, expires_in_minutes=10)
    monkeypatch.setattr(auth, "_charge_registration", nothing)
    monkeypatch.setattr(auth, "_send_verification", sent)
    monkeypatch.setattr(auth, "check_required_consents", lambda *a: None)
    monkeypatch.setattr(auth, "give_consent", nothing)


def _body(email, adult, born):
    return auth.ParticipantRegister(email=email, password="password-123", display_name="Тест",
                                    is_adult=adult, age_15_17=not adult, birth_date=born)


async def test_birth_date_is_stored_and_checked(db, quiet):
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={})
    email = f"dbtest-born-{stamp()}@example.com"
    with pytest.raises(ApiError):
        await auth.register_participant(_body(email, True, date(date.today().year - 16, 1, 1)), request, db)
    await db.rollback()
    await auth.register_participant(_body(email, True, date(1995, 5, 5)), request, db)
    await db.commit()
    person = next(p for p in await db.scalars(select(Participant).where(Participant.email.is_not(None)))
                  if p.email == email)
    try:
        assert person.birth_date == date(1995, 5, 5) and person.is_minor is False
    finally:
        await wipe_people([person.id])
