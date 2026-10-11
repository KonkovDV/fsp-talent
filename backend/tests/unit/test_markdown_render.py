"""Markdown that GitHub renders: every code fence closes on its own line."""
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
def test_fences_close_on_their_own_line(path):
    fence = None
    for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        m = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence is None:
            if m:
                fence = (m.group(1)[0], len(m.group(1)), n)
            continue
        if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and not m.group(2).strip():
            fence = None
        else:
            assert not re.search(r"\S`{3,}\s*$", line), f"{path.name}:{n}: closing fence glued to text"
    assert fence is None, f"{path.name}: fence opened at line {fence[2]} never closes"

