import redis.asyncio as aioredis

from app.core.config import settings

_pool: aioredis.ConnectionPool | None = None


def get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL, decode_responses=True, max_connections=20
        )
    return _pool


async def get_redis() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=get_pool())
