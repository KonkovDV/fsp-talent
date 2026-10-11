"""Competitor idea 8: the demo stand checks itself after the seed, before smoke changes it."""
import inspect
import re
from pathlib import Path

from seed import demo_check

ROOT = Path(__file__).resolve().parents[3]


def test_every_demo_login_in_install_is_checked():
    install = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
    source = inspect.getsource(demo_check)
    logins = set(re.findall(r"`([a-z0-9]+@(?:demo\.talent|sibcode\.demo))`", install))
    assert {"fsp001@demo.talent", "fsp002@demo.talent", "nofsp@demo.talent", "hr@sibcode.demo"} <= logins
    for login in logins:
        if login.startswith("jury"):
            assert 'f"jury{n}@demo.talent"' in source and "range(1, 11)" in source
        else:
            assert f'"{login}"' in source, login


def test_ci_runs_the_check_after_the_seed_and_before_smoke():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    seed, check, smoke = (ci.index(s) for s in ("seed.generate_seed", "seed.demo_check", "tests/smoke_api.py"))
    assert seed < check < smoke


def test_a_broken_row_fails_the_run():
    rows = [demo_check.Row("a", "b", "c", True), demo_check.Row("x", "y", "z", False)]
    table = demo_check.render(rows)
    assert "| x | y | z | СЛОМАНО |" in table and "| a | b | c | OK |" in table
