"""Seed/smoke desync: the email column is ciphertext, so SQL patterns on it never match.

v1 excluded the demo logins with `Participant.email.notin_(...)`. Against AES-GCM ciphertext that
excluded nobody: the showcase step sat a middle test for fsp002, and the smoke test, which expects a
fresh fsp002, failed. The filter now runs in Python on the decrypted address.
"""
import re
from pathlib import Path

import pytest

from app.models.participant import Participant
from seed.generate_seed import _reserved, _showcase

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(("email", "reserved"), [
    ("fsp001@demo.talent", True), ("FSP002@demo.talent", True), ("nofsp@demo.talent", True),
    ("jury3@demo.talent", True), ("extra0042@load.talent", True),
    ("showcase-backend-middle-01@demo.talent", False), ("fsp1001@demo.talent", False), (None, False),
])
def test_reserved_accounts(email, reserved):
    assert _reserved(Participant(email=email)) is reserved


def test_showcase_prefix():
    assert _showcase(Participant(email="showcase-ml-junior-03@demo.talent"), "showcase-ml-junior-")
    assert not _showcase(Participant(email="fsp001@demo.talent"))


def test_no_sql_pattern_on_the_encrypted_email_column():
    ops = "like|notlike|ilike|in_|notin_|startswith|endswith|contains"
    pattern = re.compile(rf"(Participant|Employer)\.email\.({ops})\(")
    hits = [f"{p.relative_to(ROOT)}:{n}" for base in ("app", "seed") for p in (ROOT / base).rglob("*.py")
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if pattern.search(line)]
    assert hits == []
