"""Combined coverage of the unit run and tests/integration.

Reads coverage-unit.json and coverage-integration.json when both are present,
otherwise coverage.json. Prints the three bars and exits 1 when one is missed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _norm(path: str) -> str:
    text = path.replace("\\", "/")
    if "/backend/" in text:
        return text.split("/backend/", 1)[1]
    if text.startswith("/app/"):
        return text[len("/app/"):]
    return text


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _merge(reports: list[dict]) -> dict[str, tuple[int, int]]:
    """File key -> (covered lines, statements)."""
    bucket: dict[str, tuple[set[int], set[int]]] = {}
    for report in reports:
        for path, info in report["files"].items():
            key = _norm(path)
            executed = set(info.get("executed_lines") or [])
            missing = set(info.get("missing_lines") or [])
            have = bucket.get(key)
            if have is None:
                bucket[key] = (set(executed), set(missing))
            else:
                have[0].update(executed)
                have[1].update(missing)
    out = {}
    for key, (executed, missing) in bucket.items():
        missing -= executed
        statements = executed | missing
        out[key] = (len(executed), len(statements))
    return out


def _one(report: dict) -> dict[str, tuple[int, int]]:
    out = {}
    for path, info in report["files"].items():
        summary = info["summary"]
        out[_norm(path)] = (summary["covered_lines"], summary["num_statements"])
    return out


def main() -> None:
    unit = ROOT / "coverage-unit.json"
    integration = ROOT / "coverage-integration.json"
    if unit.exists() and integration.exists():
        files = _merge([_load(unit), _load(integration)])
    else:
        files = _one(_load(ROOT / "coverage.json"))
    pipeline = files["app/services/search/pipeline.py"]
    assess = files["app/services/assessment.py"]
    covered = sum(hit for hit, _ in files.values())
    statements = sum(total for _, total in files.values())
    def layer(prefix: str) -> float:
        hit = total = 0
        for key, (got, size) in files.items():
            if key.startswith(prefix + "/") or key == prefix:
                hit += got
                total += size
        if not total:
            raise SystemExit(f"нет файлов {prefix}")
        return 100 * hit / total

    pipeline_pct = 100 * pipeline[0] / pipeline[1]
    assess_pct = 100 * assess[0] / assess[1]
    total_pct = 100 * covered / statements
    print(f"app/services {layer('app/services'):.0f}%")
    print(f"app/api {layer('app/api'):.0f}%")
    print(f"search/pipeline.py {pipeline_pct:.1f}% ({pipeline[0]}/{pipeline[1]})")
    print(f"services/assessment.py {assess_pct:.1f}% ({assess[0]}/{assess[1]})")
    print(f"app {total_pct:.2f}% ({covered}/{statements})")
    missed = []
    if pipeline_pct < 60:
        missed.append("pipeline")
    if assess_pct < 60:
        missed.append("assessment")
    if total_pct < 72:
        missed.append("app")
    if missed:
        raise SystemExit("ниже порога: " + ", ".join(missed))
    print("checks: passed")


if __name__ == "__main__":
    main()
    sys.exit(0)
