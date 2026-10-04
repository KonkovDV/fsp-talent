"""Fixed-window counter in Redis.

If Redis is down the request is allowed — a demo must still be able to log in.
"""
from __future__ import annotations

import logging

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


async def too_many(bucket: str, limit: int = 5, window_seconds: int = 60) -> bool:
    """Increment a fixed-window counter and return True when the limit is exceeded.

    Uses a pipeline to send INCR + EXPIRE(NX) in a single round-trip:
    * INCR creates the key (or bumps the count).
    * EXPIRE … NX sets the TTL *only* when the key has no existing expiry,
      i.e. immediately after INCR created it.  For an already-expiring key
      this is a no-op — the window keeps ticking.

    This closes the gap in the naive INCR / EXPIRE pair: if the process dies
    between the two commands the key would never expire, permanently blocking
    the account.  With NX the next pipeline call sets the TTL on INCR's new key.

    Requires Redis 7.0+ for the NX flag on EXPIRE (docker-compose: redis:7-alpine).
    """
    try:
        redis = await get_redis()
        pipe = redis.pipeline(transaction=False)
        pipe.incr(bucket)
        pipe.expire(bucket, window_seconds, nx=True)
        results = await pipe.execute()
        return int(results[0]) > limit
    except Exception:
        logger.exception("Rate limit skipped, Redis unavailable")
        return False
