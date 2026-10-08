"""Fail when a published test count, coverage figure or matching hash disagrees with a fresh run.

The unit-test step writes coverage.json. This check reads it, collects the tests again and
asks the matching command for the dataset hash. README, INSTALL and the pitch must quote
those three figures; VALIDATION_MATCHING.md must contain the hash the command prints.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from coverage_lines import percent

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
README = ROOT / "README.md"
INSTALL = ROOT / "docs" / "INSTALL.md"
PITCH = ROOT / "docs" / "tools" / "build_pitch.mjs"
VALIDATION = ROOT / "docs" / "VALIDATION_MATCHING.md"


def ru_tests(count: int) -> str:
    last_two = count % 100
    last = count % 10
    if last == 1 and last_two != 11:
        return "тест"
    if last in (2, 3, 4) and last_two not in (12, 13, 14):
        return "теста"
    return "тестов"


def collected_tests() -> int:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit", "--collect-only", "-q"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", env=env, check=False,
    )
    match = re.search(r"(\d+) tests collected", proc.stdout)
    if proc.returncode != 0 or not match:
        raise SystemExit(proc.stdout + proc.stderr)
    return int(match.group(1))


def matching_sha() -> str:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "app.validation.matching", "--seeds", "0"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", env=env, check=False,
    )
    match = re.search(r"^sha256 ([0-9a-f]{64})$", proc.stdout, re.M)
    if proc.returncode != 0 or not match:
        raise SystemExit(proc.stdout + proc.stderr)
    return match.group(1)


def coverage_parts() -> tuple[str, int, int]:
    report_path = BACKEND / "coverage.json"
    if not report_path.is_file():
        raise SystemExit("нет backend/coverage.json: сначала pytest --cov=app --cov-report=json")
    files = json.loads(report_path.read_text(encoding="utf-8"))
    shown = f"{files['totals']['percent_covered']:.2f}".replace(".", ",")
    return shown, percent("app/services", files["files"]), percent("app/api", files["files"])


def require(text: str, needle: str, where: str) -> None:
    if needle not in text:
        raise SystemExit(f"{where} не содержит «{needle}»")


def main() -> None:
    count = collected_tests()
    total, services, api = coverage_parts()
    digest = matching_sha()
    word = ru_tests(count)
    readme = README.read_text(encoding="utf-8")
    install = INSTALL.read_text(encoding="utf-8")
    pitch = PITCH.read_text(encoding="utf-8")
    require(readme, f"| Юнит-тесты (в CI, со всеми компиляторами) | {count} |", "README")
    require(readme, f"{count} юнит-{word}", "README")
    require(readme, f"{total} %, {services} % и {api} %", "README")
    require(install, f"собирает {count} {word}", "INSTALL")
    require(install, f"{total} % по всему приложению, сервисы {services} %, API {api} %", "INSTALL")
    require(pitch, f"{count} юнит-{word}, покрытие приложения {total} %, сервисы {services} % и API {api} %", "питч")
    require(VALIDATION.read_text(encoding="utf-8"), digest, "VALIDATION_MATCHING.md")
    print(f"doc numbers: {count} {word}, coverage {total} %, services {services} %, API {api} %, sha256 {digest}")


if __name__ == "__main__":
    main()
