"""Own-data export and the password-change gate. Secrets never leave in the file."""
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from app.models.participant import Participant
from app.services.account_export import (
    employer_record,
    participant_record,
    password_change_problem,
    without_secrets,
)


def test_secret_fields_are_stripped_at_every_level():
    clean = without_secrets({
        "email": "a@b.c",
        "password_hash": "secret",
        "nested": {"token_epoch": 3, "name": "Аня"},
        "rows": [{"code_hash": "h", "kind": "pd_candidate"}],
    })
    assert clean["email"] == "a@b.c"
    assert "password_hash" not in clean
    assert clean["nested"] == {"name": "Аня"}
    assert clean["rows"] == [{"kind": "pd_candidate"}]


def test_a_candidate_file_has_the_profile_and_not_the_password():
    person = SimpleNamespace(
        email="a@b.c", display_name="Аня", region=None, phone=None, telegram=None, fsp_id=None,
        specialization="backend", declared_grade="middle", assessed_grade="middle", experience_years=3,
        salary_from_gross=200_000, salary_to_gross=240_000, is_visible=True, job_search="open",
        birth_date=None, is_minor=False, minor_consent_given=False, guardian_email=None,
        guardian_consent_at=None, public_profile=False, password_hash="secret",
        minor_now=lambda: False,
    )
    record = participant_record(person, [], None, [], [])
    assert record["email"] == "a@b.c"
    assert record["salary_from"] == 200_000
    assert record["birth_date"] is None
    assert record["is_minor"] is False
    assert "password_hash" not in record


def test_a_minor_file_carries_the_guardian_facts_the_person_is_owed():
    teen_birth = date.today() - timedelta(days=365 * 15)  # 14 or 15 years old: a minor on any day
    teen = Participant(
        email="teen@b.c", display_name="Лена", is_visible=False, job_search="open",
        birth_date=teen_birth, is_minor=True, minor_consent_given=True,
        guardian_email="mom@b.c", guardian_consent_at=datetime(2026, 1, 2, 9, 30, tzinfo=UTC),
        public_profile=False, password_hash="secret",
    )
    record = participant_record(teen, [], None, [], [])
    assert record["birth_date"] == teen_birth.isoformat()
    assert record["is_minor"] is True
    assert record["minor_consent_given"] is True
    assert record["guardian_email"] == "mom@b.c"
    assert record["guardian_consent_at"] == "2026-01-02T09:30:00+00:00"
    assert "password_hash" not in record


def test_a_person_past_eighteen_is_not_exported_as_a_minor():
    # The stored flag is written at registration and not recalculated as the person ages; the export follows the date.
    adult = Participant(
        email="a@b.c", display_name="Аня", is_visible=True, job_search="open",
        birth_date=date(2000, 1, 1), is_minor=True, minor_consent_given=False,
        public_profile=False, password_hash="secret",
    )
    record = participant_record(adult, [], None, [], [])
    assert record["is_minor"] is False
    assert record["birth_date"] == "2000-01-01"


def test_a_company_file_names_a_candidate_only_after_consent():
    hidden = SimpleNamespace(
        role="backend", status="pending", salary_from_gross=1, salary_to_gross=2, created_at=None,
        contacts_revealed_at=None, contacts_revoked_at=None,
        candidate=SimpleNamespace(display_name="Секрет"),
    )
    company = SimpleNamespace(
        email="hr@demo.talent", company_name="Сибкод", inn=None, website=None, industry=None, description=None,
    )
    record = employer_record(company, [], [], [hidden])
    assert record["offers"][0]["candidate_name"] is None


def test_password_change_rejects_a_missing_wrong_or_repeated_password():
    assert password_change_problem(False, False, False) == "no_password"
    assert password_change_problem(True, False, False) == "bad_current"
    assert password_change_problem(True, True, True) == "same"
    assert password_change_problem(True, True, False) is None
