"""Jury accounts skip pauses and attempt limits only on the demo stand."""
from app.core.config import settings
from app.services.assessment import JURY_EMAILS, jury_unlimited


def test_jury_accounts_are_unlimited_only_with_demo_mode(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    assert len(JURY_EMAILS) == 10
    assert jury_unlimited("jury1@demo.talent") and jury_unlimited(" Jury10@demo.talent ")
    assert not jury_unlimited("jury11@demo.talent")
    assert not jury_unlimited("fsp001@demo.talent") and not jury_unlimited(None)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert not jury_unlimited("jury1@demo.talent")
