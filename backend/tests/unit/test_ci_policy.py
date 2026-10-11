"""CI runs with a read-only token and the deploy does not edit config."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CI = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"
pytestmark = pytest.mark.skipif(not CI.exists(), reason="workflows are outside the backend image")


def _ci() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def test_workflow_token_is_read_only_by_default():
    assert _ci()["permissions"] == {"contents": "read"}


def test_no_job_asks_for_write_except_oidc_signing():
    for name, job in _ci()["jobs"].items():
        for scope, level in (job.get("permissions") or {}).items():
            if level == "write":
                assert (name, scope) == ("sign-sbom", "id-token"), (name, scope)


def test_deploy_does_not_rewrite_the_server_env():
    deploy = _ci()["jobs"]["deploy"]
    script = "\n".join(step.get("with", {}).get("script", "") for step in deploy["steps"])
    assert "AI_ENABLED" not in script
    assert "deploy/.env" not in script.replace("--env-file deploy/.env", "")
    assert "sed -i" not in script
