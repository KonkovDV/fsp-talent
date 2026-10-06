"""Store a successful response under the caller's Idempotency-Key for 24 hours.

The same key and the same body return the stored response. The same key with a different body is
rejected. Redis down fails closed when a key was sent; a request without a key is unchanged.
"""
from __future__ import annotations

import hashlib
import json

from redis.exceptions import RedisError

from app.core.redis_client import get_redis

TTL_S = 24 * 3600
PENDING_S = 120


class IdempotencyConflict(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class IdempotencyUnavailable(Exception):
    pass


def fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _slot(scope: str, key: str) -> str:
    return f"idem:{scope}:{key}"


async def idem_begin(scope: str, key: str | None, digest: str) -> dict | None:
    """None means this is the first call and the caller should run. A dict is the stored response."""
    if not key:
        return None
    if len(key) > 200:
        raise IdempotencyConflict("Ключ повтора слишком длинный")
    try:
        redis = await get_redis()
        raw = await redis.get(_slot(scope, key))
    except RedisError as e:
        raise IdempotencyUnavailable from e
    if raw:
        saved = json.loads(raw)
        if saved.get("digest") != digest:
            raise IdempotencyConflict("Тот же ключ уже использован с другим запросом")
        if saved.get("pending"):
            raise IdempotencyConflict("Запрос с этим ключом ещё выполняется")
        return saved
    try:
        won = await redis.set(_slot(scope, key), json.dumps({"digest": digest, "pending": True}),
                              nx=True, ex=PENDING_S)
    except RedisError as e:
        raise IdempotencyUnavailable from e
    if not won:
        raise IdempotencyConflict("Запрос с этим ключом ещё выполняется")
    return None


async def idem_finish(scope: str, key: str | None, digest: str, status: int, body: dict) -> None:
    if not key:
        return
    try:
        redis = await get_redis()
        await redis.set(_slot(scope, key), json.dumps({"digest": digest, "status": status, "body": body},
                                                      default=str), ex=TTL_S)
    except RedisError as e:
        raise IdempotencyUnavailable from e


async def idem_abort(scope: str, key: str | None) -> None:
    if not key:
        return
    try:
        redis = await get_redis()
        await redis.delete(_slot(scope, key))
    except RedisError:
        return
