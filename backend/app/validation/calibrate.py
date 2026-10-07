"""Re-estimate item difficulty offsets from real answers: `python -m app.validation.calibrate [--min-n 30]`.

For every item key with at least --min-n answers in completed adaptive sessions, the difficulty shift δ is
the MAP estimate given each candidate's ability measured WITHOUT the item's family (so a leaked family cannot
calibrate itself easier). After a key is recalibrated its drift counters restart, because the leak monitor
compares answers with the new difficulty. Quarantined keys are left alone until a person reviews them.
"""
from __future__ import annotations

import argparse
import asyncio
import collections

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.assessment import ItemStat, TestSession, TestSessionItem
from app.services.cat import CUTS, Response, posterior
from app.services.item_monitor import calibrate_offset


async def main(min_n: int) -> None:
    from app.core.rls import bypass_rls
    bypass_rls()
    async with AsyncSessionLocal() as db:
        sessions = list(await db.scalars(select(TestSession).where(
            TestSession.engine == "cat_v2", TestSession.status == "completed")))
        rows: dict[str, list] = collections.defaultdict(list)
        for s in sessions:
            items = [it for it in await db.scalars(select(TestSessionItem).where(
                TestSessionItem.session_id == s.id)) if it.is_correct is not None and not it.excluded]
            for fam in {it.family_id for it in items}:
                others = [Response(it.a, it.b, it.c, bool(it.is_correct)) for it in items if it.family_id != fam]
                theta = posterior(others, prior_mean=CUTS[s.target_grade]).theta
                for it in items:
                    if it.family_id == fam:
                        # b already contains the old offset; estimate the shift relative to it.
                        rows[it.item_key].append((theta, it.a, it.b, it.c, bool(it.is_correct)))
        changed = 0
        for stat in await db.scalars(select(ItemStat)):
            data = rows.get(stat.item_key, [])
            if stat.status != "active" or len(data) < min_n:
                continue
            stat.b_offset += calibrate_offset(data)
            stat.n, stat.correct, stat.expected, stat.variance, stat.z = 0, 0, 0.0, 0.0, 0.0
            changed += 1
        await db.commit()
        print(f"sessions={len(sessions)} keys recalibrated={changed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-n", type=int, default=30)
    asyncio.run(main(parser.parse_args().min_n))
