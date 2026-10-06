"""The published path list is the OpenAPI surface. A new or removed route fails this test."""
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).resolve().parents[3] / "docs" / "openapi_paths.txt"


def test_openapi_paths_match_the_snapshot():
    live = "\n".join(sorted(app.openapi()["paths"])) + "\n"
    assert live == SNAPSHOT.read_text(encoding="utf-8")
