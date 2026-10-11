"""The published path list and the full document are the OpenAPI surface.

A new or removed route, or any change of a schema, fails this test until the snapshots are
regenerated: `python -m app.tools.dump_openapi > ../docs/openapi.json`.
"""
import json
from pathlib import Path

from app.main import app
from app.tools.dump_openapi import render

DOCS = Path(__file__).resolve().parents[3] / "docs"
SNAPSHOT = DOCS / "openapi_paths.txt"


def test_openapi_paths_match_the_snapshot():
    live = "\n".join(sorted(app.openapi()["paths"])) + "\n"
    assert live == SNAPSHOT.read_text(encoding="utf-8")
    # The full document as well: schemas, parameters and error codes, not only the path list.
    document = (DOCS / "openapi.json").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert render() == document, "regenerate docs/openapi.json: python -m app.tools.dump_openapi"
    assert json.loads(document)["openapi"].startswith("3.1")
