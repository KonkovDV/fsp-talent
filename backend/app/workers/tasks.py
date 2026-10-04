import asyncio
import logging
import time
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _rebuild(participant_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models import Participant
    from app.services.profile import rebuild_profile
    async with AsyncSessionLocal() as db:
        participant = await db.get(Participant, UUID(participant_id))
        if participant is None:
            logger.info(f"Skip rebuild, participant {participant_id} not found")
            return
        await rebuild_profile(db, participant)
        await db.commit()


@celery_app.task(name="app.workers.tasks.recompute_scores", bind=True, max_retries=3)
def recompute_scores(self, participant_id: str):
    try:
        run_async(_rebuild(participant_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60) from exc


@celery_app.task(name="app.workers.tasks.compute_embeddings", bind=True, max_retries=3)
def compute_embeddings(self, participant_id: str):
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
