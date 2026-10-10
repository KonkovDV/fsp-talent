"""The initial migration must apply to an empty database (CI failed on main at 5ace578).

The dump created employer_favorites with an inline FOREIGN KEY to employers before the employers primary
key existed, and a policy on need_hidden read public.needs before that table was created. Without a database
in unit tests, this checks the ordering rules that make the dump apply.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0001_initial.py"


def _module():
    spec = importlib.util.spec_from_file_location("m0001", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_create_table_keeps_an_inline_foreign_key():
    mod = _module()
    kept, deferred = mod._defer_inline_foreign_keys(mod._statements(mod._SCHEMA))
    assert deferred, "the dump has foreign keys; they must be deferred"
    for statement in kept:
        if statement.lstrip().upper().startswith("CREATE TABLE"):
            assert "FOREIGN KEY" not in statement
            assert not re.search(r",\s*\)\s*$", statement), statement[:80]
    assert all(s.startswith("ALTER TABLE ONLY public.") and " FOREIGN KEY " in s for s in deferred)


def test_every_table_exists_before_any_statement_that_names_it():
    mod = _module()
    kept, _ = mod._defer_inline_foreign_keys(mod._statements(mod._SCHEMA))
    ordered = mod._dependency_order(kept)
    created: set[str] = set()
    tables = {m.group(1) for s in ordered for m in [re.match(r"\s*CREATE TABLE public\.(\w+)", s)] if m}
    for statement in ordered:
        m = re.match(r"\s*CREATE TABLE public\.(\w+)", statement)
        if m:
            created.add(m.group(1))
            continue
        for name in re.findall(r"public\.(\w+)", statement):
            if name in tables:
                assert name in created, (name, statement[:100])
