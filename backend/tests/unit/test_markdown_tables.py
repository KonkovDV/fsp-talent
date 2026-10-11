"""Markdown that GitHub renders: every table row has as many cells as its header, so no cell is dropped."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _md_files():
    try:
        out = subprocess.check_output(["git", "ls-files", "*.md"], cwd=ROOT, text=True)
        return [ROOT / p for p in out.split()]
    except (OSError, subprocess.CalledProcessError):
        return sorted(p for p in ROOT.rglob("*.md") if "node_modules" not in p.parts)


FILES = [p for p in _md_files() if p.is_file()]


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_table_rows_match_header(path):
    header = None
    in_code = False
    for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if re.match(r"^\s*(`{3,}|~{3,})", line):
            in_code = not in_code
            continue
        s = line.strip()
        if in_code or not s.startswith("|"):
            header = None
            continue
        cells = re.sub(r"\\\|", "", re.sub(r"`[^`]*`", "C", s)).strip("|").count("|") + 1
        if header is None:
            header = (cells, n)
        else:
            assert cells == header[0], f"{path.name}:{n}: {cells} cells, header at line {header[1]} has {header[0]}"
