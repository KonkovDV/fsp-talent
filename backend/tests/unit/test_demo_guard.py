"""Demo accounts keep the printed password. A real stand is not affected."""
import pytest

from app.api.errors import ApiError
from app.core import demo_guard
from app.services.trust import complaints_that_count, should_pause


def _demo(monkeypatch, on: bool) -> None:
    monkeypatch.setattr(demo_guard.settings, "DEMO_MODE", on)
    monkeypatch.setattr(demo_guard.settings, "DEMO_PROTECTED_SUFFIXES", "@demo.talent,.demo")


def test_a_demo_account_cannot_change_the_password_or_be_deleted(monkeypatch):
    _demo(monkeypatch, True)
    with pytest.raises(ApiError) as change:
        demo_guard.reject_protected("jury1@demo.talent")
    assert change.value.status_code == 409 and change.value.code == "demo_protected"
    with pytest.raises(ApiError) as erase:
        demo_guard.reject_protected("hr@sibcode.demo")
    assert erase.value.status_code == 409


def test_the_guard_is_off_when_the_stand_is_not_a_demo(monkeypatch):
    _demo(monkeypatch, False)
    demo_guard.reject_protected("jury1@demo.talent")
    demo_guard.reject_protected("hr@sibcode.demo")


def test_a_normal_address_stays_open_on_the_demo_stand(monkeypatch):
    _demo(monkeypatch, True)
    assert demo_guard.is_protected("person@example.com") is False
    assert demo_guard.is_protected("ivan@x.demo") is False
    demo_guard.reject_protected("person@example.com")
    demo_guard.reject_reserved("ivan@x.demo")


def test_seed_refuses_when_the_stand_is_not_a_demo(monkeypatch):
    from seed import generate_seed
    monkeypatch.setattr(generate_seed.settings, "DEMO_MODE", False)
    with pytest.raises(SystemExit):
        generate_seed._refuse_production()
    monkeypatch.setattr(generate_seed.settings, "DEMO_MODE", True)
    monkeypatch.delenv("ENV", raising=False)
    generate_seed._refuse_production()


def test_mock_fsp_id_is_refused_outside_the_demo(caplog):
    from app.core.config import Settings
    with pytest.raises(RuntimeError):
        Settings(DEMO_MODE=False, FSP_ID_MODE="mock")
    with caplog.at_level("WARNING", logger="app.core.config"):
        Settings(DEMO_MODE=False, FSP_ID_MODE="oidc", MAIL_MODE="console")
    assert any("MAIL_MODE=console" in rec.message for rec in caplog.records)


def test_a_published_address_cannot_be_registered(monkeypatch):
    _demo(monkeypatch, True)
    with pytest.raises(ApiError) as caught:
        demo_guard.reject_reserved("jury1@demo.talent")
    assert caught.value.status_code == 422 and caught.value.code == "reserved_email"
    _demo(monkeypatch, False)
    demo_guard.reject_reserved("jury1@demo.talent")


def test_a_complaint_from_a_demo_account_does_not_move_the_pause(monkeypatch):
    _demo(monkeypatch, True)
    emails = ["jury1@demo.talent", "jury2@demo.talent", "fsp001@demo.talent"]
    counted = complaints_that_count(emails)
    assert counted == []
    assert should_pause(len(set(counted)), len(counted), 10) is False
    _demo(monkeypatch, False)
    counted = complaints_that_count(emails)
    assert len(counted) == 3
    assert should_pause(len(set(counted)), len(counted), 10) is True


def test_a_jury_account_is_seeded_with_an_adult_birth_date():
    from datetime import date

    from app.models import Participant
    from app.services.profile import adult_cutoff
    from seed.generate_seed import JURY_BIRTH
    assert JURY_BIRTH <= adult_cutoff(date(2026, 10, 11))
    person = Participant(is_visible=True, birth_date=JURY_BIRTH, job_search="open")
    assert person.discoverable
    source = open("seed/generate_seed.py", encoding="utf-8").read()
    assert "birth_date=JURY_BIRTH" in source
    assert "existing.birth_date = JURY_BIRTH" in source
    assert "JURY_BIRTH" in open("seed/reset_demo.py", encoding="utf-8").read()


def test_an_empty_cron_drops_the_nightly_reset(monkeypatch):
    from app.core.config import settings
    from app.workers.celery_app import demo_reset_entry
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "DEMO_RESET_CRON", "10 4 * * *")
    entry = demo_reset_entry()
    assert entry is not None and entry["task"].endswith("reset_demo")
    assert str(entry["schedule"].hour) == "{4}" and str(entry["schedule"].minute) == "{10}"
    monkeypatch.setattr(settings, "DEMO_RESET_CRON", "")
    assert demo_reset_entry() is None
    monkeypatch.setattr(settings, "DEMO_RESET_CRON", "10 4 * * *")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert demo_reset_entry() is None


def test_only_published_jury_accounts_may_self_reset():
    from app.services.demo_reset import is_jury
    assert is_jury("jury1@demo.talent") and is_jury("JURY10@demo.talent ")
    assert not is_jury("fsp001@demo.talent") and not is_jury("hr@sibcode.demo")
    assert not is_jury("jury11@demo.talent") and not is_jury("jury1@demo.talent.evil") and not is_jury(None)


def test_the_app_and_the_seed_use_the_same_jury_birth_date():
    from app.services.demo_reset import JURY_BIRTH
    from seed.generate_seed import JURY_BIRTH as SEED_BIRTH
    assert JURY_BIRTH == SEED_BIRTH
