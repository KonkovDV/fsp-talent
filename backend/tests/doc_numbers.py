"""Fail when a published test count, coverage figure or matching hash disagrees with a fresh run.

The unit-test step writes coverage.json. This check reads it, collects the tests again and
asks the matching command for the dataset hash. README, INSTALL and the pitch must quote
those three figures; VALIDATION_MATCHING.md must contain the hash the command prints.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
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


# A machine without the extra compilers covers a few different lines. 0.1 point is that gap, not a new figure.
COVERAGE_TOLERANCE = 0.2


def coverage_within(measured: float, published: float, tolerance: float = COVERAGE_TOLERANCE) -> bool:
    """True when two coverage percents are the same figure for publication."""
    return abs(measured - published) <= tolerance + 1e-9


def coverage_parts() -> tuple[float, str, int, int]:
    report_path = BACKEND / "coverage.json"
    if not report_path.is_file():
        raise SystemExit("нет backend/coverage.json: сначала pytest --cov=app --cov-report=json")
    files = json.loads(report_path.read_text(encoding="utf-8"))
    measured = float(files["totals"]["percent_covered"])
    shown = f"{measured:.1f}".replace(".", ",")
    return measured, shown, percent("app/services", files["files"]), percent("app/api", files["files"])


def _published_coverage(text: str, pattern: str) -> tuple[float, int, int] | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return float(match.group(1).replace(",", ".")), int(match.group(2)), int(match.group(3))


def require_coverage(text: str, pattern: str, measured: float, services: int, api: int, where: str) -> None:
    """Services and API must match. The application total may move by a tenth of a point."""
    found = _published_coverage(text, pattern)
    shown = f"{measured:.1f}".replace(".", ",")
    needle = f"{shown} %, {services} % и {api} %"
    if found is None or found[1] != services or found[2] != api or not coverage_within(measured, found[0]):
        raise SystemExit(f"{where} не содержит «{needle}»")


def pitch_deck_matches_html() -> None:
    """The slide images are baked into the deck. A changed pitch.html without a rebuild must fail."""
    html_path = ROOT / "docs" / "pitch.html"
    deck = ROOT / "docs" / "pitch.pptx"
    # A Windows checkout with core.autocrlf stores CRLF. The deck keeps the hash of the LF text.
    digest = hashlib.sha256(html_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    needle = f"pitch-html-sha256={digest}"
    with zipfile.ZipFile(deck) as package:
        core = package.read("docProps/core.xml").decode("utf-8")
    if needle not in core:
        raise SystemExit(
            "перерисуйте слайды: node docs/tools/build_pitch.mjs && python docs/tools/build_pitch_template.py"
        )


def require(text: str, needle: str, where: str) -> None:
    if needle not in text:
        raise SystemExit(f"{where} не содержит «{needle}»")


# These sentences described the product before the profile-discipline weight. The code now uses it.
STALE_DISCIPLINE = (
    "Отдельного веса 0,5",
    "пониженным весом не считается",
)


def forbid_stale_discipline_claims() -> None:
    paths = [README, *sorted((ROOT / "docs").glob("*.md"))]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for phrase in STALE_DISCIPLINE:
            if phrase in text:
                raise SystemExit(f"{path.relative_to(ROOT)} содержит устаревшую фразу «{phrase}»")


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


def forbid_stale_method_names() -> None:
    """A point estimate of θ̂ is not an M-step. A participation that scores 0 can still lower the bound."""
    roots = [ROOT / "backend" / "app", ROOT / "backend" / "tests", ROOT / "docs", ROOT / "README.md"]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        else:
            files.extend(path for path in root.rglob("*") if path.suffix in {".py", ".md"})
    for path in files:
        if path.name == "doc_numbers.py":
            continue
        if any(part in {".venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "M-step of MML-EM" in text:
            raise SystemExit(f"{path} содержит «M-step of MML-EM»")
        if "never lifts the mean" in text and "does not lower" not in text:
            raise SystemExit(f"{path} содержит «never lifts the mean» без «does not lower»")


def main() -> None:
    forbid_stale_discipline_claims()
    forbid_stale_method_names()
    count = collected_tests()
    measured, total, services, api = coverage_parts()
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
    require(readme, "| Максимальная доля одного ключа внутри специализации | 69 % |", "README")
    require(readme, f"{count} юнит-{word}", "README")
    require_coverage(readme, r"(\d+,\d+) %, (\d+) % и (\d+) %", measured, services, api, "README")
    require(install, f"собирает {count} {word}", "INSTALL")
    require_coverage(
        install, r"(\d+,\d+) % по всему приложению, сервисы (\d+) %, API (\d+) %",
        measured, services, api, "INSTALL",
    )
    require_coverage(
        pitch, r"покрытие приложения (\d+,\d+) %, сервисы (\d+) % и API (\d+) %",
        measured, services, api, "питч",
    )
    require(VALIDATION.read_text(encoding="utf-8"), digest, "VALIDATION_MATCHING.md")
    pitch_deck_matches_html()
    require_method_figures(readme)
    print(f"doc numbers: {count} {word}, coverage {total} %, services {services} %, API {api} %, sha256 {digest}")


if __name__ == "__main__":
    main()
