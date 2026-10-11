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


async def stale_participant_ids(db, max_age_hours: float | None = None) -> list:
    """Old scoring version, or (nightly) computed more than max_age_hours ago.

    Decay runs from the date of the computation, so a score left alone for a month compares
    candidates against different reference dates (audit 2026-10, item 5). The nightly pass fixes that.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import or_, select

    from app.models.profile import DisciplineScore
    from app.services.scoring.engine import VERSION

    stale = DisciplineScore.scoring_version != VERSION
    if max_age_hours is not None:
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        stale = or_(stale, DisciplineScore.computed_at < cutoff, DisciplineScore.computed_at.is_(None))
    rows = await db.execute(select(DisciplineScore.participant_id).where(stale).distinct())
    return list(rows.scalars())


async def rescore_stale(max_age_hours: float | None = None) -> tuple[int, int]:
    from app.core.database import AsyncSessionLocal
    from app.core.rls import bypass_rls, reset_rls
    from app.models.participant import Participant
    from app.services.profile import rebuild_profile
    from app.workers.tasks import _acquire_rebuild_lock, _release_rebuild_lock

    # A system job, like the worker (tasks.run_async). Without the bypass the rebuild cannot see
    # FORCE-RLS tables such as candidate_resumes and writes a search row without the resume stack.
    scope = bypass_rls()
    try:
        return await _rescore(max_age_hours, AsyncSessionLocal, Participant, rebuild_profile,
                              _acquire_rebuild_lock, _release_rebuild_lock)
    finally:
        reset_rls(scope)


async def _rescore(max_age_hours, AsyncSessionLocal, Participant, rebuild_profile, acquire, release):
    async with AsyncSessionLocal() as db:
        ids = await stale_participant_ids(db, max_age_hours)
    done = failed = 0
    for pid in ids:
        # The same per-participant lock as the worker: a deploy start must not race a queued rebuild.
        if not await acquire(str(pid)):
            continue
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
        finally:
            await release(str(pid))
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
