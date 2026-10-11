"""Stored scores of an older method are recomputed on start (PR #243 follow-up)."""
from pathlib import Path

from app.core import rescore_stale
from app.services.scoring import engine

ROOT = Path(__file__).resolve().parents[3]


def test_the_container_rescores_after_schema_sync_and_before_serving():
    cmd = next(line for line in (ROOT / "backend/Dockerfile").read_text().splitlines() if line.startswith("CMD"))
    assert cmd.index("schema_sync") < cmd.index("app.core.rescore_stale") < cmd.index("uvicorn")


def test_the_stale_query_compares_with_the_current_version():
    import inspect

    assert "!= VERSION" in inspect.getsource(rescore_stale.stale_participant_ids)
    assert engine.VERSION == "v4.0.0"


def test_a_failure_never_blocks_the_start(monkeypatch):
    async def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(rescore_stale, "rescore_stale", boom)
    assert rescore_stale.main() == 0
