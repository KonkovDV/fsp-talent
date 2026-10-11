"""Audit 2026-10 M-6: facts in the docs match the code and the law."""
from pathlib import Path

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[3]


def test_salary_floor_is_the_2026_minimum_wage_everywhere():
    # Federal Law of 28.11.2025 No. 429-FZ: 27 093 ₽ a month from 1 January 2026.
    assert settings.MIN_MONTHLY_GROSS == 27_093
    dialog = (ROOT / "frontend/src/components/InviteDialog.tsx").read_text("utf-8")
    # audit-3 P1-2: the form reads the floor from GET /public/limits, the number is not copied there.
    assert "27093" not in dialog and "getLimits" in dialog
    assert "22 440" not in (ROOT / "docs/TRUST_AND_ATS.md").read_text("utf-8")


def test_readme_names_the_real_password_hash():
    readme = (ROOT / "README.md").read_text("utf-8")
    assert "Пароли — bcrypt" not in readme and "Пароли — Argon2id" in readme
    assert "argon2" in (ROOT / "backend/app/core/security.py").read_text("utf-8").lower()


def test_ai_discipline_is_documented_as_outside_the_official_list():
    doc = (ROOT / "docs/FSP_INTEGRATION.md").read_text("utf-8")
    assert "шести дисциплин" not in doc and "расширение вне ВРВС" in doc
