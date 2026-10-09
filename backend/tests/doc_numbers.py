"""Fail when the published matching figures disagree with a fresh run.

README must quote P@10 of the full model and the resume sort.
VALIDATION_MATCHING.md must contain the dataset hash the command prints.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
README = ROOT / "README.md"
VALIDATION = ROOT / "docs" / "VALIDATION_MATCHING.md"


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


def require(text: str, needle: str, where: str) -> None:
    if needle not in text:
        raise SystemExit(f"{where} не содержит «{needle}»")


def main() -> None:
    digest, precision = matching_report()
    readme = README.read_text(encoding="utf-8")
    require(
        readme,
        f"| Доля подходящих в первой десятке, P@10 на трёх зёрнах: полная модель и по резюме | {precision} |",
        "README",
    )
    require(VALIDATION.read_text(encoding="utf-8"), digest, "VALIDATION_MATCHING.md")
    print(f"doc numbers: P@10 {precision}, sha256 {digest}")


if __name__ == "__main__":
    main()
