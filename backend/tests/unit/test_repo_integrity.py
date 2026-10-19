"""Guards against the failure classes found in the 2026-10-05 review.

Two commits replaced source files with their base64 text (backend/app/services/assessment.py,
frontend/src/store/authStore.ts), and one migration pointed at a revision id that does not exist.
Unit tests passed in all three cases because nothing imported the broken module or walked the
migration graph. These tests do.
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import re
import subprocess
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".css", ".yml", ".yaml", ".toml", ".ini", ".sh", ".conf", ".sql"}
_B64_CHAR = re.compile(rb"[A-Za-z0-9+/=]")


def _tracked_sources() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
        files = [REPO / line for line in out.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        files = [p for p in REPO.rglob("*") if ".git" not in p.parts and "node_modules" not in p.parts]
    return [p for p in files if p.suffix in SOURCE_SUFFIXES and p.is_file()]


def test_no_source_file_is_a_base64_blob():
    blobs = []
    for path in _tracked_sources():
        data = path.read_bytes().strip()
        # One long line that is (almost) all base64 alphabet. "Almost": the corrupted assessment.py
        # had a single stray "(" in 14.5 KB, which a strict full match would miss.
        if len(data) >= 200 and b"\n" not in data and len(_B64_CHAR.findall(data)) / len(data) > 0.99:
            blobs.append(str(path.relative_to(REPO)))
    assert not blobs, f"Files committed as base64 text instead of source: {blobs}"


def test_every_backend_module_imports():
    os.environ.setdefault("SECRET_KEY", "unit-test-secret-not-a-published-placeholder")
    import app

    failed = {}
    for mod in pkgutil.walk_packages(app.__path__, prefix="app."):
        try:
            importlib.import_module(mod.name)
        except Exception as e:  # noqa: BLE001 - report every broken module, not just the first
            failed[mod.name] = f"{type(e).__name__}: {e}"[:200]
    assert not failed, failed


def test_alembic_graph_has_one_head_and_no_dangling_parent():
    pytest.importorskip("alembic")
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())  # raises if a down_revision does not exist
    assert [item.revision for item in revisions] == ["0001_initial"]
    assert script.get_heads() == ["0001_initial"]
    assert len(script.get_bases()) == 1
    schema = (BACKEND / "alembic" / "versions" / "0001_initial.py").read_text(encoding="utf-8")
    assert "uq_participants_email_bindex" in schema and "uq_employers_email_bindex" in schema
    assert "participants_email_key" not in schema and "employers_email_key" not in schema
    assert "show_city boolean DEFAULT true NOT NULL" in schema


def test_secret_looking_paths_are_not_the_application_page():
    """A scanner must not get index.html with status 200 for /.env or /.git."""
    caddy = (REPO / "deploy" / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    assert "@hidden path /.env /.env.* /.git /.git/**" in caddy
    assert 'respond "Not Found" 404' in caddy
    nginx = (REPO / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "return 404;" in nginx
    assert r"^/\.(env|git)($|/|\.)" in nginx
    compose = (REPO / "deploy" / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "ACME_EMAIL" in compose
    assert "empty address must not be written" in compose
