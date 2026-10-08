"""Shared shortlist cache.

The ranking depends on the need and the candidate bank, not on which company is looking.
A company's own marks are applied after the cache is read, so one employer never sees another's.
"""
from __future__ import annotations

import asyncio
import hashlib
import json

from app.core.redis_client import get_redis

EPOCH_KEY = "search-bank-epoch"
TTL_S = 300
# Bump when the ranking rule changes, so a cached order from the previous rule is not served.
RANK_VERSION = 2
# Matches allows offset <= 200 and limit <= 50. One stored ranking covers every page.
WINDOW = 250
_COMPANY_KEYS = ("shortlisted", "invited", "contacts_closed")


def shortlist_key(need_id: object, version: int, epoch: int) -> str:
    return f"shortlist:v{RANK_VERSION}:{need_id}:{version}:{epoch}"


def shared_key(params: dict, epoch: int) -> str:
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"shortlist-shared:v{RANK_VERSION}:{digest}:{epoch}"


def store_payload(result: dict) -> dict:
    """Drop company marks. `complete` is false when the pool was longer than the stored window."""
    ranked = [{k: v for k, v in item.items() if k not in _COMPANY_KEYS} for item in result["items"]]
    payload = {k: v for k, v in result.items() if k != "items"}
    payload["ranked"] = ranked
    payload["complete"] = len(ranked) < WINDOW
    return payload


def slice_ranked(stored: dict, offset: int, limit: int) -> dict | None:
    """One page of a stored ranking. None when this page was not saved."""
    ranked = stored.get("ranked")
    if not isinstance(ranked, list):
        return None
    if offset + limit > len(ranked) and not stored.get("complete"):
        return None
    page = {k: v for k, v in stored.items() if k not in ("ranked", "complete")}
    page["items"] = [dict(item) for item in ranked[offset:offset + limit]]
    return page


def apply_company_marks(items: list[dict], shortlisted: set[str], offers: dict[str, dict]) -> None:
    """Marks of the company that asked. Another company's offers are not in `offers`."""
    for card in items:
        cid = card["candidate_id"]
        mark = offers.get(cid) or {}
        card["shortlisted"] = cid in shortlisted
        card["invited"] = bool(mark.get("invited"))
        card["contacts_closed"] = bool(mark.get("contacts_closed"))


async def bank_epoch(redis) -> int:
    raw = await redis.get(EPOCH_KEY)
    return int(raw or 0)


async def bump_bank_epoch() -> None:
    """Invalidate every shortlist. A failure leaves the previous epoch; the TTL still expires it."""
    try:
        redis = await get_redis()
        await redis.incr(EPOCH_KEY)
    except Exception:
        return


async def read_ranked(redis, key: str) -> dict | None:
    raw = await redis.get(key)
    if not raw:
        return None
    return json.loads(raw)


async def write_ranked(redis, key: str, payload: dict) -> None:
    await redis.set(key, json.dumps(payload), ex=TTL_S)


async def wait_ranked(redis, key: str, attempts: int = 25) -> dict | None:
    """Another worker is already ranking this need. Wait for its result."""
    for _ in range(attempts):
        found = await read_ranked(redis, key)
        if found is not None:
            return found
        await asyncio.sleep(0.1)
    return None
