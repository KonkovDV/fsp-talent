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
FIGURES = ROOT / "frontend" / "src" / "methodFigures.ts"


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


def _ru3(value: str) -> str:
    return f"{float(value):.3f}".replace(".", ",")


def matching_report() -> tuple[str, str]:
    """Hash of the seed-2026 set and P@10 of the full model versus the resume sort, over three seeds."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "app.validation.matching"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", env=env, check=False,
    )
    digest = re.search(r"^sha256 ([0-9a-f]{64})$", proc.stdout, re.M)
    model = re.search(
        r"^\| ФСП Талант: оценка соответствия \| [0-9.]+ ± [0-9.]+ \| ([0-9.]+) ±",
        proc.stdout, re.M)
    base = re.search(
        r"^\| Базовая линия «по резюме»: заявленные навыки и грейд \| [0-9.]+ ± [0-9.]+ \| ([0-9.]+) ±",
        proc.stdout, re.M)
    if proc.returncode != 0 or not digest or not model or not base:
        raise SystemExit(proc.stdout + proc.stderr)
    return digest.group(1), f"{_ru3(model.group(1))} и {_ru3(base.group(1))}"


def coverage_parts() -> tuple[str, int, int]:
    report_path = BACKEND / "coverage.json"
    if not report_path.is_file():
        raise SystemExit("нет backend/coverage.json: сначала pytest --cov=app --cov-report=json")
    files = json.loads(report_path.read_text(encoding="utf-8"))
    # Two decimals move between machines (66.41 here, 66.43 in CI). One decimal is the figure both runs share.
    shown = f"{files['totals']['percent_covered']:.1f}".replace(".", ",")
    return shown, percent("app/services", files["files"]), percent("app/api", files["files"])


def require(text: str, needle: str, where: str) -> None:
    if needle not in text:
        raise SystemExit(f"{where} не содержит «{needle}»")


def method_figure_values() -> list[str]:
    """The first quoted string of each row on the method page."""
    text = FIGURES.read_text(encoding="utf-8")
    start = text.index("export const FIGURES")
    body = text[start:text.index("\n]", start)]
    return re.findall(r"'([^']*)'", body)[::3]


def require_method_figures(readme: str) -> None:
    """Each method-page figure must sit in the README numbers table, not inside a larger number."""
    start = readme.index("## Цифры, которые можно проверить")
    section = readme[start:]
    section = section[:section.index("\n## ", 3)]
    for value in method_figure_values():
        if re.search(rf"(?<![\d,]){re.escape(value)}", section) is None:
            raise SystemExit(f"README не содержит «{value}»")


def main() -> None:
    count = collected_tests()
    total, services, api = coverage_parts()
    digest, precision = matching_report()
    word = ru_tests(count)
    readme = README.read_text(encoding="utf-8")
    install = INSTALL.read_text(encoding="utf-8")
    pitch = PITCH.read_text(encoding="utf-8")
    require(
        readme,
        f"| Доля подходящих в первой десятке, P@10 на трёх зёрнах: полная модель и по резюме | {precision} |",
        "README",
    )
    require(readme, f"| Юнит-тесты (в CI, со всеми компиляторами) | {count} |", "README")
    require(readme, f"{count} юнит-{word}", "README")
    require(readme, f"{total} %, {services} % и {api} %", "README")
    require(install, f"собирает {count} {word}", "INSTALL")
    require(install, f"{total} % по всему приложению, сервисы {services} %, API {api} %", "INSTALL")
    require(pitch, f"{count} юнит-{word}, покрытие приложения {total} %, сервисы {services} % и API {api} %", "питч")
    require(VALIDATION.read_text(encoding="utf-8"), digest, "VALIDATION_MATCHING.md")
    require_method_figures(readme)
    print(f"doc numbers: {count} {word}, coverage {total} %, services {services} %, API {api} %, sha256 {digest}")


if __name__ == "__main__":
    main()
