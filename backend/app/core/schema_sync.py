"""Bring a database created by an older 0001_initial up to the current one.

The schema lives in a single revision, so `alembic upgrade` does nothing on a volume that is
already at 0001_initial. This step runs after it on every start. It reads the same SQL, compares
it with the catalog and adds only what is missing: tables with their indexes, row-level security
and policies, columns, constraints and indexes of existing tables. It never drops or alters
anything that exists. A statement that fails (a NOT NULL column on a table with rows, data that
breaks a new constraint) is logged and skipped; the rest still runs.
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("app.core.schema_sync")

MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0001_initial.py"
_IDENT = r'"?([A-Za-z_][A-Za-z0-9_]*)"?'
_TABLE = re.compile(r"^CREATE TABLE public\.(\w+) \((.*)\)$", re.S)
_INDEX = re.compile(r"^CREATE (?:UNIQUE )?INDEX (\w+) ON public\.(\w+)", re.S)
_CONSTRAINT = re.compile(r"^ALTER TABLE (?:ONLY )?public\.(\w+)\s+ADD CONSTRAINT (\w+)", re.S)
_RLS = re.compile(r"^ALTER TABLE (?:ONLY )?public\.(\w+) (?:ENABLE|FORCE) ROW LEVEL SECURITY$", re.S)
_POLICY = re.compile(r"^CREATE POLICY (\w+) ON public\.(\w+)", re.S)
_COLUMN = re.compile(r"^" + _IDENT + r"\s+(.+)$", re.S)


@dataclass
class Catalog:
    tables: set[str] = field(default_factory=set)
    columns: dict[str, set[str]] = field(default_factory=dict)
    indexes: set[str] = field(default_factory=set)
    constraints: set[str] = field(default_factory=set)
    policies: set[str] = field(default_factory=set)


def _split_body(body: str) -> list[str]:
    """Top-level comma-separated items of a CREATE TABLE body."""
    items, buf, depth, quoted = [], [], 0, False
    for ch in body:
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        if ch == "," and depth == 0 and not quoted:
            items.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if "".join(buf).strip():
        items.append("".join(buf).strip())
    return items


def plan(statements: list[str], have: Catalog) -> list[str]:
    """Statements that add what the catalog lacks, in the order of the schema."""
    out: list[str] = []
    new_tables: set[str] = set()
    for stmt in statements:
        if stmt.startswith("CREATE FUNCTION"):
            continue
        if m := _TABLE.match(stmt):
            table, body = m.group(1), m.group(2)
            if table not in have.tables:
                new_tables.add(table)
                out.append(stmt)
                continue
            for item in _split_body(body):
                if item.startswith("CONSTRAINT "):
                    name = item.split()[1]
                    if name not in have.constraints:
                        out.append(f"ALTER TABLE public.{table} ADD {item}")
                elif (col := _COLUMN.match(item)) and col.group(1) not in have.columns.get(table, set()):
                    out.append(f"ALTER TABLE public.{table} ADD COLUMN IF NOT EXISTS {item}")
            continue
        if m := _INDEX.match(stmt):
            if m.group(1) not in have.indexes:
                out.append(stmt)
            continue
        if m := _CONSTRAINT.match(stmt):
            if m.group(2) not in have.constraints:
                out.append(stmt)
            continue
        if m := _RLS.match(stmt):
            if m.group(1) in new_tables:
                out.append(stmt)
            continue
        if m := _POLICY.match(stmt):
            if m.group(1) not in have.policies:
                out.append(stmt)
            continue
        logger.warning("schema_sync: statement kind not handled: %s", stmt[:80])
    return out


def schema_statements() -> list[str]:
    spec = importlib.util.spec_from_file_location("_initial_schema", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module._statements(module._SCHEMA)


async def _catalog(conn) -> Catalog:
    have = Catalog()
    for row in await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"):
        have.tables.add(row["tablename"])
    for row in await conn.fetch(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"):
        have.columns.setdefault(row["table_name"], set()).add(row["column_name"])
    for row in await conn.fetch("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"):
        have.indexes.add(row["indexname"])
    for row in await conn.fetch(
            "SELECT c.conname FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
            "WHERE n.nspname = 'public'"):
        have.constraints.add(row["conname"])
    for row in await conn.fetch("SELECT policyname FROM pg_policies WHERE schemaname = 'public'"):
        have.policies.add(row["policyname"])
    return have


def _owner_dsn() -> str:
    url = os.environ.get("MIGRATE_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("нет адреса владельца базы")
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def sync(dsn: str | None = None, dry_run: bool = False) -> tuple[int, int]:
    """Apply the plan. Returns (applied, failed). A dry run prints the plan and changes nothing."""
    import asyncpg

    conn = await asyncpg.connect(dsn or _owner_dsn())
    try:
        if not await conn.fetchval("SELECT to_regclass('public.alembic_version') IS NOT NULL"):
            return 0, 0
        todo = plan(schema_statements(), await _catalog(conn))
        if dry_run:
            for stmt in todo:
                print(stmt.splitlines()[0][:160])
            return len(todo), 0
        applied = failed = 0
        for stmt in todo:
            try:
                async with conn.transaction():
                    await conn.execute(stmt)
                applied += 1
                logger.warning("schema_sync: applied %s", stmt.splitlines()[0][:120])
            except Exception as exc:
                failed += 1
                logger.error("schema_sync: skipped %s (%s)", stmt.splitlines()[0][:120], type(exc).__name__)
        if applied and await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = 'fsp_app'"):
            await conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fsp_app")
            await conn.execute("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO fsp_app")
        return applied, failed
    finally:
        await conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        applied, failed = asyncio.run(sync(dry_run="--dry-run" in sys.argv))
    except Exception:
        logger.exception("schema_sync: не удалось сверить схему")
        sys.exit(1)
    logger.warning("schema_sync: добавлено %d, пропущено %d", applied, failed)


if __name__ == "__main__":
    main()
