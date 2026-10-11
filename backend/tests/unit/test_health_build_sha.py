"""/health names the build commit, so the jury can match the stand to a commit."""
from pathlib import Path

import pytest

from app import main

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(("value", "expected"), [
    ("0123456789abcdef0123456789abcdef01234567", "0123456789abcdef0123456789abcdef01234567"),
    ("ABCDEF1", "abcdef1"),
    ("", "unknown"),
    ("main; rm -rf /", "unknown"),
    ("<script>", "unknown"),
])
def test_build_sha_is_a_bare_hex_or_unknown(monkeypatch, value, expected):
    monkeypatch.setenv("GIT_SHA", value)
    assert main.build_sha() == expected


async def test_health_reports_the_build(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "abc1234")
    body = await main.health()
    assert body["build"] == "abc1234" and body["status"] == "ok"


def test_the_build_passes_the_commit_everywhere():
    assert "ARG GIT_SHA" in (ROOT / "backend/Dockerfile").read_text()
    assert "GIT_SHA: ${GIT_SHA:-unknown}" in (ROOT / "docker-compose.yml").read_text()
    assert "git rev-parse HEAD" in (ROOT / "Makefile").read_text()
    assert "--build-arg GIT_SHA=${{ github.sha }}" in (ROOT / ".github/workflows/ci.yml").read_text()
