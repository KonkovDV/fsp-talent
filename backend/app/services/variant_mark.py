"""A typed answer that matches another variant of the same family is a review mark.

The grade is not changed here. Families whose keys collide too often are skipped:
a shared number is then not evidence.
"""
from __future__ import annotations

import random
from collections import Counter
from functools import lru_cache

from app.items import same_number, typed_answer
from app.items.registry import FAMILIES

SAMPLES = 60
COLLISION_MAX = 0.02


def collision_rate(keys: list[str]) -> float:
    """Share of pairs that carry the same key."""
    total = len(keys) * (len(keys) - 1) // 2
    if total == 0:
        return 1.0
    pairs = sum(count * (count - 1) // 2 for count in Counter(keys).values())
    return pairs / total


@lru_cache(maxsize=256)
def _sample_keys(family_id: str, spec: str, level: int) -> tuple[str, ...] | None:
    fam = FAMILIES.get(family_id)
    if fam is None or fam.kind != "code" or not fam.available(spec, level):
        return None
    rng = random.Random(f"variant:{family_id}:{spec}:{level}")
    keys: list[str] = []
    for _ in range(SAMPLES):
        try:
            item = fam.generate(rng, level, spec)
        except Exception:
            return None
        key = typed_answer(fam.kind, item)
        if key:
            keys.append(key)
    if len(keys) < SAMPLES // 2 or collision_rate(keys) >= COLLISION_MAX:
        return None
    return tuple(keys)


def foreign_variant(family_id: str, spec: str, level: int, own_right: str, typed: str) -> bool:
    """True when a wrong typed answer is the key of some other variant."""
    text = (typed or "").strip()
    if not text or same_number(text, own_right):
        return False
    keys = _sample_keys(family_id, spec, level)
    if not keys:
        return False
    return any(same_number(text, key) for key in keys)
