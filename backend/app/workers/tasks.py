import asyncio
import logging
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
            await db.execute(update(Offer).where(
                Offer.status == "pending", Offer.expires_at < datetime.now(UTC)).values(status="expired"))
            await db.commit()
    run_async(_inner())
