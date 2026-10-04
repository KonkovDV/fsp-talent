"""Fixed-window counter in Redis. If Redis is down, the request is allowed: a demo must still log in."""
from __future__ import annotations

import logging

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


async def too_many(bucket: str, limit: int = 5, window_seconds: int = 60) -> bool:
    try:
        redis = await get_redis()
        count = await redis.incr(bucket)
        if count == 1:
            await redis.expire(bucket, window_seconds)
        return int(count) > limit
    except Exception:
        logger.exception("Rate limit skipped, Redis unavailable")
        return False
