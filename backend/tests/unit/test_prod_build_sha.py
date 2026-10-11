"""The production stand reports the deployed commit in /health."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_every_backend_image_in_prod_gets_the_commit():
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.prod.yml").read_text(encoding="utf-8"))
    backends = [s for s in compose["services"].values()
                if isinstance(s.get("build"), dict) and s["build"]["context"] == "../backend"]
    assert len(backends) == 3
    assert all(s["build"]["args"]["GIT_SHA"] == "${GIT_SHA:-unknown}" for s in backends)
    assert not [s for s in compose["services"].values() if s.get("build") == "../backend"]


def test_the_deploy_passes_the_commit():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "GIT_SHA=$(git rev-parse HEAD) docker compose -f deploy/docker-compose.prod.yml" in ci
