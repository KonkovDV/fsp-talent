"""Demo stand without mail: the confirmation code is shown only with DEMO_MODE and DEMO_SHOW_CODE together."""
import asyncio
from types import SimpleNamespace

import pytest

from app.api.v1 import auth
from app.core.config import settings


class _Db:
    async def commit(self):
        return None


@pytest.fixture
def sent(monkeypatch):
    letters = []

    async def issue_code(db, role, account_id, email, purpose):
        return "123456", "tok"

    async def send_code(email, role, purpose, code, token):
        letters.append(code)

    monkeypatch.setattr(auth, "issue_code", issue_code)
    monkeypatch.setattr(auth, "send_code", send_code)

    def run(demo_mode, show_code):
        monkeypatch.setattr(settings, "DEMO_MODE", demo_mode)
        monkeypatch.setattr(settings, "DEMO_SHOW_CODE", show_code)
        account = SimpleNamespace(id=1)
        return asyncio.run(auth._send_verification(_Db(), "participant", account, "a@example.com")), letters
    return run


def test_no_flags_no_code(sent):
    answer, letters = sent(False, False)
    assert answer.demo_code is None and letters == ["123456"]


def test_both_flags_show_the_issued_code(sent):
    answer, letters = sent(True, True)
    assert answer.demo_code == "123456" == letters[-1]


def test_show_code_ignored_outside_demo(sent):
    answer, _ = sent(False, True)
    assert answer.demo_code is None


def test_demo_mode_alone_keeps_code_in_the_letter(sent):
    answer, _ = sent(True, False)
    assert answer.demo_code is None


def test_public_demo_reports_only_the_flag(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    assert client.get("/api/v1/public/demo").json() == {"demo_mode": True}
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert client.get("/api/v1/public/demo").json() == {"demo_mode": False}
