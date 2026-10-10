"""A wider look at the same posterior. The list still uses the lower bound.

mu and sigma are the shipped discipline posterior. This span does not replace them.
"""
from __future__ import annotations


def elo_stretch(mu: float, sigma: float) -> dict:
    low = max(0.0, min(1.0, mu - sigma))
    high = max(0.0, min(1.0, mu + sigma))
    if high < low:
        high = low
    return {"low": round(low, 2), "high": round(high, 2)}
