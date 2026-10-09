"""The jury button offers the address that has been idle the longest, and nothing else."""
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import public
from app.core.config import settings

EARLY = datetime(2026, 10, 1, tzinfo=UTC)
LATE = datetime(2026, 10, 9, tzinfo=UTC)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    async def scalars(self, _stmt):
        return self.rows


def _person(email, stamp, deleted_at=None):
    return SimpleNamespace(email=email, last_login_at=stamp, deleted_at=deleted_at)


def test_never_used_beats_an_old_stamp_and_a_tie_takes_the_lower_number():
    assert public.free_jury_email({
        "jury5@demo.talent": EARLY,
        "jury2@demo.talent": EARLY,
        "jury9@demo.talent": None,
    }) == "jury9@demo.talent"
    assert public.free_jury_email({
        "jury5@demo.talent": EARLY,
        "jury2@demo.talent": EARLY,
        "jury8@demo.talent": LATE,
    }) == "jury2@demo.talent"
    assert public.free_jury_email({}) is None


@pytest.mark.asyncio
async def test_the_endpoint_returns_only_the_address(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    rows = [
        _person("jury2@demo.talent", LATE),
        _person("jury7@demo.talent", None),
        _person("jury3@demo.talent", EARLY),
        _person("jury4@demo.talent", None, deleted_at=EARLY),
        _person("not-jury@demo.talent", None),
    ]
    body = await public.jury_free(_Rows(rows))
    assert body == {"email": "jury7@demo.talent"}


@pytest.mark.asyncio
async def test_the_endpoint_is_absent_outside_the_demo(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    with pytest.raises(HTTPException) as missing:
        await public.jury_free(_Rows([]))
    assert missing.value.status_code == 404


@pytest.mark.asyncio
async def test_the_endpoint_is_absent_when_no_jury_account_exists(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with pytest.raises(HTTPException) as missing:
        await public.jury_free(_Rows([]))
    assert missing.value.status_code == 404
