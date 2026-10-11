"""Write the OpenAPI document of the app with sorted keys (NEW-16).

    python -m app.tools.dump_openapi > ../docs/openapi.json

The file lets a reader of the repository or the PDF see every route, schema and error code without
the stand. `tests/unit/test_openapi_paths.py` fails when the app and the file drift apart.
"""
from __future__ import annotations

import json
import sys


def render() -> str:
    from app.main import app

    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render())
