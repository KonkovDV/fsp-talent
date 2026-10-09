"""Email identity, consents and the error format (no database needed)."""
import ast
import hashlib
import re
from pathlib import Path

import pytest

from app.api.errors import ERROR_CODES, ApiError, error_body
from app.legal import documents, get_document, required_kinds
from app.services.identity import letter

ROOT = Path(__file__).resolve().parents[2]


def test_legal_documents_parse_and_hash_their_body():
    docs = documents()
    assert {"terms", "pd_candidate", "pd_employer", "pd_distribution"} <= set(docs)
    for doc in docs.values():
        assert doc.sha256 == hashlib.sha256(doc.body_md.encode()).hexdigest()
        assert re.fullmatch(r"\d+\.\d+", doc.version)


def test_personal_data_consent_is_a_separate_document():
    # 152-FZ art. 9 (156-FZ): consent cannot be a clause inside the terms of use.
    assert set(required_kinds("participant")) == {"terms", "pd_candidate"}
    assert set(required_kinds("employer")) == {"terms", "pd_employer"}
    assert "согласие" not in get_document("terms").title.lower()
    assert not get_document("pd_distribution").required


def test_api_error_rejects_unregistered_codes():
    with pytest.raises(ValueError):
        ApiError(400, "made_up_code")
    err = ApiError(403, "email_not_verified", details={"email": "a@b.ru"})
    assert err.detail == ERROR_CODES["email_not_verified"]
    body = error_body(err.code, err.detail, err.details)
    assert body["error"]["code"] == "email_not_verified" and body["detail"] == err.detail


def _codes_used_in_app() -> set[str]:
    used = set()
    for path in (ROOT / "app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "ApiError":
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    used.add(node.args[1].value)
    return used


def test_every_raised_code_is_registered_and_documented():
    used = _codes_used_in_app()
    assert used, "no ApiError calls found"
    assert used <= set(ERROR_CODES), used - set(ERROR_CODES)
    documented = set(re.findall(r"^\| `([a-z_0-9]+)` \|", (ROOT.parent / "docs/API_ERRORS.md").read_text(), re.M))
    assert set(ERROR_CODES) == documented, set(ERROR_CODES) ^ documented


def test_the_code_stays_in_the_body_and_the_link_token_stays_out_of_the_query():
    subject, text = letter("participant", "verify", "123456", "sekret")
    assert "123456" not in subject
    assert "123456" in text
    assert "/verify#token=sekret" in text
    assert "?" not in text
    reset_subject, reset_text = letter("employer", "reset", "654321", "other")
    assert "654321" not in reset_subject
    assert "654321" in reset_text


def test_login_and_contacts_use_the_confirmed_email():
    src = (ROOT / "app/api/v1/auth.py").read_text(encoding="utf-8")
    assert "email_not_verified" in src
    profile = (ROOT / "app/api/v1/candidates.py").read_text(encoding="utf-8")
    assert "email: EmailStr" not in profile, "the login email must not be editable without confirmation"
