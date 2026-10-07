"""Print coverage of the two layers the review asks for, after pytest --cov=app --cov-report=json."""
import json
from pathlib import Path


def percent(prefix: str, files: dict) -> int:
    statements = covered = 0
    for path, info in files.items():
        norm = path.replace("\\", "/")
        if norm.startswith(prefix + "/") or f"/{prefix}/" in f"/{norm}":
            summary = info["summary"]
            statements += summary["num_statements"]
            covered += summary["covered_lines"]
    if not statements:
        raise SystemExit(f"нет файлов {prefix} в coverage.json")
    return round(100 * covered / statements)


def main() -> None:
    report = Path(__file__).resolve().parents[1] / "coverage.json"
    files = json.loads(report.read_text(encoding="utf-8"))["files"]
    print(f"app/services {percent('app/services', files)}%")
    print(f"app/api {percent('app/api', files)}%")


if __name__ == "__main__":
    main()
