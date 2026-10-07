from pathlib import Path

from app.validation.jury_pack import load_pack, validate_rows

RESOURCES = Path(__file__).resolve().parents[2] / "app" / "validation" / "resources"


def test_a_pack_names_the_two_roles_that_can_log_in():
    rows = [
        {"email": "a@demo.talent", "role": "participant", "display_name": "Анна", "grade": "junior"},
        {"email": "hr@demo.talent", "role": "employer", "company": "Пример"},
    ]
    assert validate_rows(rows) == []


def test_the_shipped_pack_names_the_demo_accounts_and_does_not_invent_a_role():
    for name in ("jury_profiles.json", "jury_profiles.csv"):
        rows = load_pack(RESOURCES / name)
        assert validate_rows(rows) == []
        assert {row["role"] for row in rows} == {"participant", "employer"}


def test_an_unknown_role_and_a_repeated_email_are_rejected():
    rows = [
        {"email": "a@demo.talent", "role": "jury", "display_name": "Жюри"},
        {"email": "a@demo.talent", "role": "participant", "display_name": "Анна", "grade": "lead"},
    ]
    errors = validate_rows(rows)
    assert any("роль" in line for line in errors)
    assert any("повторяется" in line for line in errors)
