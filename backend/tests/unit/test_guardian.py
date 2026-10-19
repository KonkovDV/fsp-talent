"""Guardian consent link: bound to the participant and to the exact email the minor named."""
import uuid

from app.core.config import settings
from app.services.guardian import (
    consent_link,
    demo_consent_link,
    guardian_token,
    same_person_mailbox,
    token_participant,
    token_valid,
)


def test_link_is_bound_to_the_person_and_the_email():
    pid = uuid.uuid4()
    token = guardian_token(pid, "Mama@Example.ru")
    assert token_participant(token) == pid
    assert token_valid(token, pid, "mama@example.ru")
    assert not token_valid(token, pid, "other@example.ru")
    assert not token_valid(token, uuid.uuid4(), "mama@example.ru")
    assert not token_valid(token, pid, None)
    assert token_participant("garbage") is None


def test_a_plus_alias_of_the_child_is_not_a_guardian():
    assert same_person_mailbox("child@example.com", "child+parent@example.com")
    assert same_person_mailbox("a.b@gmail.com", "ab@googlemail.com")
    assert not same_person_mailbox("child@example.com", "parent@example.com")
    assert not same_person_mailbox("child@example.com", None)


def test_an_old_or_spent_guardian_link_dies():
    pid = uuid.uuid4()
    fresh = guardian_token(pid, "mama@example.ru", generation=1, issued_at=1_700_000_000)
    assert token_valid(fresh, pid, "mama@example.ru", generation=1, now=1_700_000_000 + 60)
    assert not token_valid(fresh, pid, "mama@example.ru", generation=1, now=1_700_000_000 + 8 * 24 * 3600)
    assert not token_valid(fresh, pid, "mama@example.ru", generation=2, now=1_700_000_000 + 60)
    assert not token_valid(fresh + "aa", pid, "mama@example.ru", generation=1, now=1_700_000_000 + 60)


def test_the_consent_link_keeps_the_token_out_of_the_query():
    link = consent_link("https://talent.example", "abc.def")
    assert link == "https://talent.example/guardian#token=abc.def"
    assert "?" not in link


def test_the_demo_screen_shows_the_link_only_for_an_ordinary_address(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "DEMO_SHOW_CODE", True)
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://stand.example")
    monkeypatch.setattr(settings, "DEMO_PROTECTED_SUFFIXES", "@demo.talent,.demo")
    pid = uuid.uuid4()
    link = demo_consent_link(pid, "Mama@Example.ru")
    assert link is not None and link.startswith("https://stand.example/guardian#token=")
    assert "?" not in link
    assert demo_consent_link(pid, "jury1@demo.talent") is None
    assert demo_consent_link(pid, "hr@sibcode.demo") is None
    monkeypatch.setattr(settings, "DEMO_SHOW_CODE", False)
    assert demo_consent_link(pid, "mama@example.ru") is None
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "DEMO_SHOW_CODE", True)
    assert demo_consent_link(pid, "mama@example.ru") is None
