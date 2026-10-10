"""Roles that are not chosen in the product. A methodist is granted from the server console."""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.services.ai.assistant import has_identity


def release_key(row, note: str, now) -> None:
    if row.status != "quarantined":
        raise ValueError("not_quarantined")
    if has_identity(note):
        raise ValueError("identity")
    row.status = "active"
    row.quarantined_at = None
    row.updated_at = now


async def set_methodist(email: str, on: bool) -> bool:
    from app.core.database import AsyncSessionLocal
    from app.core.rls import bypass_rls
    from app.models import Employer
    from app.services.field_cipher import blind_index

    bypass_rls()
    async with AsyncSessionLocal() as db:
        employer = await db.scalar(select(Employer).where(
            Employer.email_bindex == blind_index(email.strip().lower())))
        if employer is None:
            return False
        employer.is_methodist = on
        await db.commit()
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Роль методиста")
    parser.add_argument("command", choices=("grant", "revoke"))
    parser.add_argument("role", choices=("methodist",))
    parser.add_argument("email")
    args = parser.parse_args()
    found = asyncio.run(set_methodist(args.email, args.command == "grant"))
    print("Роль обновлена" if found else f"Компания {args.email.strip()} не найдена")


if __name__ == "__main__":
    main()
