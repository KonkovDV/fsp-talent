"""Every test name and path cited in docs/REQUIREMENTS_QA.md must exist."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
DOC = ROOT / "docs" / "REQUIREMENTS_QA.md"


def _cited():
    return re.findall(r"`([^`]+)`", DOC.read_text(encoding="utf-8"))


def test_every_cited_test_exists():
    defined = set()
    for f in (ROOT / "backend" / "tests").rglob("test_*.py"):
        defined |= set(re.findall(r"def (test_\w+)", f.read_text(encoding="utf-8")))
    names = [c for c in _cited() if re.fullmatch(r"test_\w+", c)]
    assert len(names) >= 25
    assert [n for n in names if n not in defined] == []


def test_every_cited_path_exists():
    paths = [c for c in _cited() if "/" in c and " " not in c]
    assert paths
    assert [p for p in paths if not (ROOT / p).exists()] == []
