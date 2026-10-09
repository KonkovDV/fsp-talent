"""Let fsp_app log in, so the API does not connect as the database owner.

The migration creates the role without a password. When APP_DB_PASSWORD is set, the
container grants LOGIN after alembic and the application URL uses that role. A local
run leaves the variable empty and keeps its own login. The password is not logged.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys

logger = logging.getLogger("app.core.app_login")

_HEX = re.compile(r"[0-9a-fA-F]{32,128}")


def login_statement(password: str) -> str:
    if _HEX.fullmatch(password) is None:
        raise ValueError("пароль роли fsp_app должен быть шестнадцатеричным, от 32 до 128 знаков")
    return f"ALTER ROLE fsp_app WITH LOGIN PASSWORD '{password}'"


def _owner_dsn() -> str:
    url = os.environ.get("MIGRATE_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("нет адреса владельца базы")
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def enable() -> None:
    password = os.environ.get("APP_DB_PASSWORD", "").strip()
    if not password:
        return
    import asyncpg

    statement = login_statement(password)
    conn = await asyncpg.connect(_owner_dsn())
    try:
        await conn.execute(statement)
    finally:
        await conn.close()


def main() -> None:
    try:
        asyncio.run(enable())
    except Exception:
        logger.error("не удалось выдать вход роли fsp_app")
        sys.exit(1)


if __name__ == "__main__":
    main()
