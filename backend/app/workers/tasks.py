import asyncio
import logging
import time
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_REBUILD_LOCK_TTL = 600  # seconds
_REBUILD_LOCK_PREFIX = "rebuild_lock:"


def run_async(coro):
    from app.core.rls import bypass_rls, reset_rls
    loop = asyncio.new_event_loop()
    scope = bypass_rls()
    try:
        return loop.run_until_complete(coro)
    finally:
        reset_rls(scope)
        loop.close()


async def _acquire_rebuild_lock(participant_id: str) -> bool:
    """Try to set a Redis NX key for this participant. Returns True if lock acquired."""
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        key = f"{_REBUILD_LOCK_PREFIX}{participant_id}"
        # SET key 1 NX EX ttl: atomic, returns True when set, None when already exists.
        acquired = await redis.set(key, "1", nx=True, ex=_REBUILD_LOCK_TTL)
        return bool(acquired)
    except Exception:
        logger.warning("rebuild_lock: Redis unavailable, proceeding without lock")
        return True  # fail-open: allow the rebuild to run


async def _release_rebuild_lock(participant_id: str) -> None:
    try:
        from app.core.redis_client import get_redis
        redis = await get_redis()
        await redis.delete(f"{_REBUILD_LOCK_PREFIX}{participant_id}")
    except Exception:
        logger.warning("rebuild_lock: could not release lock for %s", participant_id)


async def _rebuild(participant_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models import Participant
    from app.services.profile import rebuild_profile

    if not await _acquire_rebuild_lock(participant_id):
        logger.info("rebuild_lock: skipping duplicate rebuild for %s", participant_id)
        return
    try:
        async with AsyncSessionLocal() as db:
            participant = await db.get(Participant, UUID(participant_id))
            if participant is None:
                logger.info("Skip rebuild, participant %s not found", participant_id)
                return
            await rebuild_profile(db, participant)
            await db.commit()
    finally:
        await _release_rebuild_lock(participant_id)


@celery_app.task(name="app.workers.tasks.recompute_scores", bind=True, max_retries=3)
def recompute_scores(self, participant_id: str):
    try:
        run_async(_rebuild(participant_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60) from exc


@celery_app.task(name="app.workers.tasks.compute_embeddings", bind=True, max_retries=3)
def compute_embeddings(self, participant_id: str):
    # NOTE: rebuild_profile calls embed() when EMBEDDINGS_MODE != 'off'.
    # When embeddings are disabled this task is a no-op beyond the score rebuild,
    # which is safe (idempotent) and cheap.  The lock prevents double work.
    try:
        run_async(_rebuild(participant_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120) from exc


@celery_app.task(name="app.workers.tasks.expire_offers")
def expire_offers():
    async def _inner():
        from datetime import UTC, datetime

        from sqlalchemy import update

        from app.core.database import AsyncSessionLocal
        from app.models.offer import Offer
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Offer)
                .where(Offer.status == "pending", Offer.expires_at < datetime.now(UTC))
                .values(status="expired"),
            )
            await db.commit()
    run_async(_inner())


@celery_app.task(name="app.workers.tasks.offer_weekly_tasks")
def offer_weekly_tasks():
    """TZ 2.1: once a week offer every active candidate one short task from an employer's vacancy."""
    async def _inner():
        from app.core.database import AsyncSessionLocal
        from app.services.practice import offer_weekly_tasks as offer
        async with AsyncSessionLocal() as db:
            sent, outbox = await offer(db)
            await db.commit()
            await outbox.deliver()
            logger.info("offer_weekly_tasks: offered %d tasks", sent)
    run_async(_inner())


@celery_app.task(name="app.workers.tasks.sync_fsp_changes")
def sync_fsp_changes():
    """Re-read FSP protocols that appeared after the last cursor. Linked accounts only."""
    async def _inner():
        from app.core.database import AsyncSessionLocal
        from app.core.redis_client import get_redis
        from app.services.fsp.mock import get_fsp_adapter
        from app.services.fsp.sync import pull_registry_changes
        async with AsyncSessionLocal() as db:
            from app.services.fsp.sync import remember_cursor
            redis = await get_redis()
            updated, nxt = await pull_registry_changes(db, redis, get_fsp_adapter())
            await db.commit()
            await remember_cursor(redis, nxt)
            if updated:
                logger.info("sync_fsp_changes: updated %d profiles", updated)
    run_async(_inner())


@celery_app.task(name="app.workers.tasks.purge_withdrawn")
def purge_withdrawn():
    """Erase candidates 30 days after they withdrew the processing consent (152-FZ, art. 21, part 5)."""
    async def _inner():
        from app.core.database import AsyncSessionLocal
        from app.services.privacy import purge_withdrawn as purge
        async with AsyncSessionLocal() as db:
            erased = await purge(db)
            await db.commit()
            if erased:
                logger.info("purge_withdrawn: erased %d candidates", erased)
    run_async(_inner())


@celery_app.task(name="app.workers.tasks.purge_guests")
def purge_guests():
    """Close what demo guests left after their 48 hours (services/guest.py)."""
    async def _inner():
        from app.core.database import AsyncSessionLocal
        from app.services.guest import purge_guests as purge
        async with AsyncSessionLocal() as db:
            closed = await purge(db)
            await db.commit()
            if closed:
                logger.info("purge_guests: closed %d rows", closed)
    run_async(_inner())


@celery_app.task(name="app.workers.tasks.refresh_grade_fail_rates")
def refresh_grade_fail_rates():
    """Nightly π: the share who fail the first attempt at a declared grade, by specialization."""
    async def _inner():
        from app.core.database import AsyncSessionLocal
        from app.services.grade_posterior import measure_fail_rates, write_fail_rates

        async with AsyncSessionLocal() as db:
            overall, cells = await measure_fail_rates(db)
            await write_fail_rates(overall, cells)
            return {"pi0": overall, "cells": len(cells)}

    return run_async(_inner())


@celery_app.task(name="app.workers.tasks.watchdog_stuck_tasks")
def watchdog_stuck_tasks():
    """Revoke tasks running longer than task_soft_time_limit (300 s).

    Belt-and-suspenders: Celery's soft/hard time limits already send SIGTERM/SIGKILL
    automatically, but if a C-extension or blocking OS call absorbs those signals the
    watchdog ensures the slot is eventually freed.  Runs every 5 minutes via beat.
    """
    threshold = celery_app.conf.task_soft_time_limit or 300
    now = time.time()
    try:
        active = celery_app.control.inspect(timeout=5).active() or {}
    except Exception:
        logger.exception("Watchdog: worker inspect failed")
        return
    revoked = []
    for worker, tasks in active.items():
        for task in tasks:
            t_start = task.get("time_start")
            if t_start and (now - t_start) > threshold:
                celery_app.control.revoke(task["id"], terminate=True, signal="SIGKILL")
                revoked.append({
                    "id": task["id"],
                    "name": task.get("name"),
                    "worker": worker,
                    "running_s": round(now - t_start),
                })
    if revoked:
        logger.warning("Watchdog revoked %d stuck task(s): %s", len(revoked), revoked)
    else:
        logger.info("Watchdog: no stuck tasks (threshold=%ds)", threshold)


@celery_app.task(name="app.workers.tasks.reset_demo")
def reset_demo():
    """Nightly return of the jury stand. Does nothing when the demo mode is off."""
    from app.core.config import settings
    if not settings.DEMO_MODE:
        logger.info("reset_demo: DEMO_MODE is off, nothing to do")
        return
    from seed.reset_demo import reset_demo as run
    run_async(run())
