"""Regression for #264: every contact the smoke test and the e2e journeys send passes the whitelist."""
import re
from pathlib import Path

from app.services.contact import contact_ok

ROOT = Path(__file__).resolve().parents[3]


def test_fixture_contacts_pass_the_whitelist():
    smoke = (ROOT / "backend/tests/smoke_api.py").read_text(encoding="utf-8")
    e2e = (ROOT / "frontend/e2e/journeys.spec.ts").read_text(encoding="utf-8")
    found = re.findall(r'"contact_method": "([^"]+)"', smoke) + re.findall(r"contact_method: '([^']+)'", e2e)
    assert found
    assert [c for c in found if not contact_ok(c)] == []
