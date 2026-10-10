"""The same posterior the lower bound comes from. The list still uses mu − sigma.

mu and sigma are the shipped discipline posterior. This display does not replace them.
"""
from __future__ import annotations


def elo_stretch(mu: float, sigma: float) -> dict:
    sigma = abs(float(sigma))
    center = max(0.0, min(1.0, float(mu)))
    low = max(0.0, min(1.0, center - sigma))
    high = max(0.0, min(1.0, center + sigma))
    if high < low:
        high = low
    return {
        "mu": round(center, 2),
        "sigma": round(min(sigma, 1.0), 2),
        "low": round(low, 2),
        "high": round(high, 2),
    }
