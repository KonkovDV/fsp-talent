"""Parent parameters of an automatically generated item.

A session draws a new isomorph: new numbers, strings and code. The score uses the parent of that
family and level, not a difficulty fitted to the one clone and not a discrimination fitted to answers.
The parent discrimination is Family.a (a prior). The parent difficulty is LEVEL_B[level].
"""
from __future__ import annotations

from app.items import LEVEL_B, Family


def parent(family: Family, level: int, offset: float = 0.0) -> tuple[float, float]:
    """Return (a, b) for every isomorph of this family at this level.

    `offset` is the bank's difficulty shift for the key, when one is stored. It is not a new `a`.
    """
    return family.a, LEVEL_B[level] + offset
