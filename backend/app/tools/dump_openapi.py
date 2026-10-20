"""Write the OpenAPI document of the app with sorted keys.

    python -m app.tools.dump_openapi --write

`--write` rewrites `docs/openapi.json` and the path list `docs/openapi_paths.txt` (UTF-8, LF), the same
bytes on every OS. Without it the document goes to stdout. The files let a reader of the repository or
the PDF see every route, schema and error code without the stand. `tests/unit/test_openapi_paths.py`
fails when the app and the files drift apart.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[3] / "docs"


def render() -> str:
    from app.main import app

    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def paths() -> str:
    from app.main import app

    return "\n".join(sorted(app.openapi()["paths"])) + "\n"


def write(docs: Path = DOCS) -> None:
    (docs / "openapi.json").write_text(render(), encoding="utf-8", newline="\n")
    (docs / "openapi_paths.txt").write_text(paths(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    if "--write" in sys.argv[1:]:
        write()
    else:
        sys.stdout.write(render())
