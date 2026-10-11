"""Recompute FSP scores stored by an older scoring version (audit 2026-10, PR #243).

`DisciplineScore` rows keep `scoring_version`. When the method changes (v3.2.0 -> v4.0.0 made the
axis monotone), an existing volume would keep showing old numbers until each profile changed.
This step runs on every start after `schema_sync` and in the seed. It rebuilds only participants
with a stale row, the same way the worker does, so it is idempotent and cheap on a fresh stand.
A failure for one participant is logged and the rest still run; the API starts regardless.
"""
from __future__ import annotations

import asyncio
import logging
import sys

logger = logging.getLogger("app.core.rescore_stale")


async def stale_participant_ids(db) -> list:
    from sqlalchemy import select

    from app.models.profile import DisciplineScore
    from app.services.scoring.engine import VERSION

    rows = await db.execute(
        select(DisciplineScore.participant_id).where(DisciplineScore.scoring_version != VERSION).distinct()
    )
    return list(rows.scalars())


async def rescore_stale() -> tuple[int, int]:
    from app.core.database import AsyncSessionLocal
    from app.models.participant import Participant
    from app.services.profile import rebuild_profile

    async with AsyncSessionLocal() as db:
        ids = await stale_participant_ids(db)
    done = failed = 0
    for pid in ids:
        try:
            async with AsyncSessionLocal() as db:
                participant = await db.get(Participant, pid)
                if participant is not None:
                    await rebuild_profile(db, participant)
                    await db.commit()
                    done += 1
        except Exception:  # noqa: BLE001 - one bad profile must not block the start
            failed += 1
            logger.exception("rescore failed for %s", pid)
    return done, failed


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        done, failed = asyncio.run(rescore_stale())
    except Exception:  # noqa: BLE001
        logger.exception("rescore skipped")
        return 0
    logger.info("rescored %d participants with an old scoring version, %d failed", done, failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
