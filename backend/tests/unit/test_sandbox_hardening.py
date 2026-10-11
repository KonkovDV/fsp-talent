"""Audit M-1: sandbox defaults are secure; the socket is not world-accessible."""
import re
from pathlib import Path

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[3]


def test_local_fallback_needs_an_explicit_opt_out(monkeypatch):
    monkeypatch.delenv("SANDBOX_REQUIRED", raising=False)
    assert Settings.model_fields["SANDBOX_REQUIRED"].default is True


def test_python_children_get_no_processes():
    runner = (ROOT / "sandbox/runner.py").read_text("utf-8")
    assert "resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))" in runner


def test_socket_is_owner_and_group_only():
    server = (ROOT / "sandbox/server.py").read_text("utf-8")
    assert "0o666" not in server and "& 0o770" in server
    docker = (ROOT / "sandbox/Dockerfile").read_text("utf-8")
    assert "groupadd --gid 10001" in docker and "--gid 10001" in docker
    for compose in ("docker-compose.yml", "deploy/docker-compose.prod.yml"):
        text = (ROOT / compose).read_text("utf-8")
        backend = re.search(r"\n  backend:\n(.*?)\n  \w+:\n", text, re.S).group(1)
        assert 'group_add: ["10001"]' in backend, compose


def test_ci_opts_out_explicitly():
    assert "SANDBOX_REQUIRED: 'false'" in (ROOT / ".github/workflows/ci.yml").read_text("utf-8")
