"""Demo stand self-check: every demo account still shows the case INSTALL.md promises.

    python -m seed.demo_check        # after seed; exit 1 if any row fails

Prints «account → expected → fact». Read-only. Competitor idea 8 (demo as a contract).
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import func, select

from app.models import Employer, Need, Offer, Participant, Result
from app.services.field_cipher import email_is


@dataclass
class Row:
    account: str
    expected: str
    fact: str
    ok: bool


async def _person(db, email: str):
    return await db.scalar(select(Participant).where(email_is(Participant, email)))


async def _count(db, stmt) -> int:
    return int(await db.scalar(stmt) or 0)


async def check(db) -> list[Row]:
    rows: list[Row] = []

    fsp001 = await _person(db, "fsp001@demo.talent")
    if fsp001 is None:
        rows.append(Row("fsp001@demo.talent", "есть", "нет аккаунта", False))
    else:
        results = await _count(db, select(func.count()).select_from(Result).where(Result.participant_id == fsp001.id))
        pending = await _count(db, select(func.count()).select_from(Offer).where(
            Offer.candidate_id == fsp001.id, Offer.status == "pending"))
        fact = f"fsp_id={'да' if fsp001.fsp_id else 'нет'}, строк={results}"
        rows.append(Row("fsp001@demo.talent", "ФСП ID и результаты протоколов", fact,
                        bool(fsp001.fsp_id) and results > 0))
        rows.append(Row("fsp001@demo.talent", "ожидающие приглашения", f"{pending}", pending > 0))

    fsp002 = await _person(db, "fsp002@demo.talent")
    fact = (f"{fsp002.specialization}, fsp_id={'да' if fsp002.fsp_id else 'нет'}" if fsp002
            else "нет аккаунта")
    rows.append(Row("fsp002@demo.talent", "специализация security, есть ФСП", fact,
                    bool(fsp002 and fsp002.specialization == "security" and fsp002.fsp_id)))

    nofsp = await _person(db, "nofsp@demo.talent")
    rows.append(Row("nofsp@demo.talent", "без ФСП ID", "нет аккаунта" if nofsp is None else
                    f"fsp_id={'да' if nofsp.fsp_id else 'нет'}", bool(nofsp and not nofsp.fsp_id)))

    for n in range(1, 11):
        email = f"jury{n}@demo.talent"
        p = await _person(db, email)
        ok = bool(p and p.birth_date and not p.is_minor)
        rows.append(Row(email, "дата рождения указана, взрослый",
                        "нет аккаунта" if p is None else f"birth_date={'да' if p.birth_date else 'нет'}", ok))

    hr = await db.scalar(select(Employer).where(email_is(Employer, "hr@sibcode.demo")))
    if hr is None:
        rows.append(Row("hr@sibcode.demo", "есть", "нет аккаунта", False))
    else:
        needs = await _count(db, select(func.count()).select_from(Need).where(Need.employer_id == hr.id))
        statuses = set(await db.scalars(select(Offer.status).where(Offer.employer_id == hr.id).distinct()))
        rows.append(Row("hr@sibcode.demo", "три потребности", f"{needs}", needs >= 3))
        rows.append(Row("hr@sibcode.demo", "приглашения в статусах pending/accepted/rejected",
                        ", ".join(sorted(statuses)) or "нет", {"pending", "accepted", "rejected"} <= statuses))
    return rows


def render(rows: list[Row]) -> str:
    lines = ["| Аккаунт | Ожидается | Факт | Итог |", "|---|---|---|---|"]
    lines += [f"| {r.account} | {r.expected} | {r.fact} | {'OK' if r.ok else 'СЛОМАНО'} |" for r in rows]
    return "\n".join(lines)


async def _main() -> int:
    from app.core.database import AsyncSessionLocal
    from app.core.rls import bypass_rls
    bypass_rls()   # a read-only operator check across every tenant, like the seed itself
    async with AsyncSessionLocal() as db:
        rows = await check(db)
    print(render(rows))
    bad = [r for r in rows if not r.ok]
    print(f"\nДемо-стенд: {len(rows) - len(bad)}/{len(rows)} OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
