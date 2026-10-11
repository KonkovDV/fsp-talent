"""Jury local run: `docker compose up -d --build --wait` on a fresh clone, no .env, no make, no manual seed."""
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
BASE = REPO / "docker-compose.yml"
pytestmark = pytest.mark.skipif(not BASE.exists(), reason="compose files are outside the backend image")


def _svc():
    return yaml.safe_load(BASE.read_text(encoding="utf-8"))["services"]


def test_env_file_optional_with_example_fallback():
    for name in ("backend", "worker", "beat", "demo-seed"):
        files = _svc()[name]["env_file"]
        assert {"path": ".env.example", "required": True} in files, name
        assert {"path": ".env", "required": False} in files, name
        assert files.index({"path": ".env", "required": False}) > files.index(
            {"path": ".env.example", "required": True}), "own .env must override the example"


def test_demo_seed_runs_after_healthy_api_and_reports_health():
    seed = _svc()["demo-seed"]
    assert seed["depends_on"]["backend"]["condition"] == "service_healthy"
    assert "seed.generate_seed" in " ".join(seed["command"])
    assert "healthcheck" in seed, "--wait must wait for the seed"


def test_backend_image_built_once():
    svc = _svc()
    tag = svc["backend"]["image"]
    assert "build" in svc["backend"]
    for name in ("worker", "beat", "demo-seed"):
        assert svc[name]["image"] == tag and "build" not in svc[name]
        assert svc[name]["pull_policy"] == "never"


def test_host_ports_configurable_and_loopback():
    svc = _svc()
    assert svc["backend"]["ports"] == ["127.0.0.1:${API_PORT:-8010}:8000"]
    assert svc["frontend"]["ports"] == ["127.0.0.1:${FRONTEND_PORT:-3010}:80"]
    assert svc["mailpit"]["ports"] == ["127.0.0.1:${MAIL_PORT:-8025}:8025"]
    assert svc["nginx"]["ports"] == ["${HTTP_PORT:-80}:80"]
    assert "ports" not in svc["postgres"] and "ports" not in svc["redis"]
