"""Audit-4 F-11: README, INSTALL and DESIGN publish one number of UI tests."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_ui_test_count_is_the_same_everywhere():
    readme = re.search(r"\| Тесты интерфейса \| (\d+) \|", (ROOT / "README.md").read_text(encoding="utf-8"))
    install = re.search(r"Тестов интерфейса (\d+),", (ROOT / "docs/INSTALL.md").read_text(encoding="utf-8"))
    design = re.search(r"(\d+) модульн\w+ тест\w* Vitest", (ROOT / "docs/DESIGN.md").read_text(encoding="utf-8"))
    assert readme and install and design
    assert readme.group(1) == install.group(1) == design.group(1)
