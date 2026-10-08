"""Fixed-window counter in Redis.

Search and invitations stay available when Redis is down. Login, registration and mail
must not: pass fail_closed=True and handle RateLimitUnavailable as HTTP 503.
"""
from __future__ import annotations

import logging

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


class RateLimitUnavailable(RuntimeError):
    """Redis did not answer a limit that is not allowed to fail open."""


async def current_attempts(bucket: str, *, fail_closed: bool = False) -> int:
    """How many attempts are already in the window. Does not count this request."""
    try:
        redis = await get_redis()
        raw = await redis.get(bucket)
        return int(raw or 0)
    except Exception as e:
        logger.warning("Rate limit unavailable for %s", bucket, exc_info=True)
        if fail_closed:
            raise RateLimitUnavailable(bucket) from e
        return 0


async def too_many(bucket: str, limit: int = 5, window_seconds: int = 60, *, fail_closed: bool = False) -> bool:
    """Increment a fixed-window counter and return True when the limit is exceeded.

    Uses a pipeline to send INCR + EXPIRE(NX) in a single round-trip:
    * INCR creates the key (or bumps the count).
    * EXPIRE … NX sets the TTL *only* when the key has no existing expiry,
      i.e. immediately after INCR created it.  For an already-expiring key
      this is a no-op — the window keeps ticking.

    This closes the gap in the naive INCR / EXPIRE pair: if the process dies
    between the two commands the key would never expire, permanently blocking
    the account.  With NX the next pipeline call sets the TTL on INCR's new key.

    Requires Redis 7.0+ for the NX flag on EXPIRE (docker-compose: redis:7.2-alpine).
    """
    try:
        redis = await get_redis()
        pipe = redis.pipeline(transaction=False)
        pipe.incr(bucket)
        pipe.expire(bucket, window_seconds, nx=True)
        results = await pipe.execute()
        return int(results[0]) > limit
    except Exception as e:
        logger.warning("Rate limit unavailable for %s", bucket, exc_info=True)
        if fail_closed:
            raise RateLimitUnavailable(bucket) from e
        return False
