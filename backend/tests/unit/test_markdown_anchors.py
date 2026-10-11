"""Relative links in .md point to files that exist and to headings that exist (GitHub slug rules)."""
import os
import re
import subprocess
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FENCE = re.compile(r"^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", re.S | re.M)


def _md_files():
    try:
        out = subprocess.check_output(["git", "ls-files", "*.md"], cwd=ROOT, text=True)
        return [ROOT / p for p in out.split()]
    except (OSError, subprocess.CalledProcessError):
        return sorted(p for p in ROOT.rglob("*.md") if "node_modules" not in p.parts)


FILES = [p for p in _md_files() if p.is_file()]


def _slug(heading: str) -> str:
    text = re.sub(r"<[^>]+>", "", heading).strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    text = FENCE.sub("", path.read_text(encoding="utf-8"))
    found, seen = set(), {}
    for m in re.finditer(r"^#{1,6}\s+(.+?)\s*#*$", text, re.M):
        base = _slug(m.group(1))
        n = seen.get(base, 0)
        seen[base] = n + 1
        found.add(base if n == 0 else f"{base}-{n}")
    found.update(re.findall(r'<a\s+(?:name|id)="([^"]+)"', text))
    return found


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(path):
    text = FENCE.sub("", path.read_text(encoding="utf-8"))
    broken = []
    for url in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z]+:", url):
            continue
        target, _, frag = url.partition("#")
        dest = Path(os.path.normpath(path.parent / urllib.parse.unquote(target))) if target else path
        if target and not dest.exists():
            broken.append(url)
        elif frag and dest.suffix == ".md" and urllib.parse.unquote(frag).lower() not in _anchors(dest):
            broken.append(url)
    assert not broken, f"{path.relative_to(ROOT)}: {broken}"
