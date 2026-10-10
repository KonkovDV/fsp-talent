"""Monthly pay after NDFL. Stored amounts stay gross; this only converts for display and for a candidate
who typed a take-home figure.

Scale of Tax Code art. 224 in force since 2025, applied to the year's pay (12 times the monthly amount)
and assuming no other income that year:
13% up to 2.4 million, 15% up to 5, 18% up to 20, 20% up to 50, 22% above.
The result is rounded to 100 rubles.
"""
from __future__ import annotations

# Upper edge of a band in rubles per year, and the rate on the slice up to that edge.
_BANDS: tuple[tuple[int | None, int], ...] = (
    (2_400_000, 13),
    (5_000_000, 15),
    (20_000_000, 18),
    (50_000_000, 20),
    (None, 22),
)
_CAP = 100_000_000


def annual_tax(income: int) -> int:
    tax, prev = 0, 0
    for edge, rate in _BANDS:
        if income <= prev:
            break
        top = income if edge is None else min(income, edge)
        tax += (top - prev) * rate // 100
        if edge is None or income <= edge:
            break
        prev = edge
    return tax


def net_monthly(gross_monthly: int) -> int:
    """Take-home pay for one month, rounded to 100 rubles."""
    if gross_monthly <= 0:
        return 0
    annual = gross_monthly * 12
    monthly = (annual - annual_tax(annual)) / 12
    return int(round(monthly / 100) * 100)


def as_gross(amount: int, basis: str) -> int:
    """Store and compare a fork before tax. A take-home figure is converted first."""
    if basis == "net":
        return gross_for_net(amount)
    return amount


def gross_for_net(net: int) -> int:
    """Smallest gross whose take-home, after rounding, is at least `net`."""
    if net <= 0:
        return 0
    lo, hi = net, max(net, 1)
    while net_monthly(hi) < net and hi < _CAP:
        hi = min(hi * 2, _CAP)
    best = hi
    while lo <= hi:
        mid = (lo + hi) // 2
        if net_monthly(mid) < net:
            lo = mid + 1
        else:
            best, hi = mid, mid - 1
    return best
