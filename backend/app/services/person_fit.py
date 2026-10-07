"""Person-fit of one finished session.

lz is the standardized log-likelihood of the answer pattern at the ability estimate
(Drasgow, Levine and Williams, 1985). lz* removes the part of that likelihood that was
used to estimate the ability itself (Snijders, 2001): the covariance of the likelihood
with the score is partialled out, and the variance shrinks by the same regression.

A value below −1.645 is the one-sided 5 % point of the standard normal. It is a reason
to offer another attempt. It is not a finding that the person cheated.
"""
from __future__ import annotations

import math

from app.services.cat import Response, p3

LZ_FLAG = -1.645


def person_fit(responses: list[Response], theta: float) -> tuple[float, float]:
    """Return (lz, lz*). Both are 0 when the pattern carries no information."""
    l0 = expected = variance = score = cov = info = 0.0
    for item in responses:
        p = min(max(p3(theta, item.a, item.b, item.c), 1e-6), 1.0 - 1e-6)
        q = 1.0 - p
        u = 1.0 if item.correct else 0.0
        log_odds = math.log(p / q)
        l0 += u * math.log(p) + (1.0 - u) * math.log(q)
        expected += p * math.log(p) + q * math.log(q)
        variance += p * q * log_odds * log_odds
        if item.c >= 1.0:
            continue
        star = (p - item.c) / (1.0 - item.c)
        dp = item.a * (1.0 - item.c) * star * (1.0 - star)
        weight = dp / (p * q)
        score += (u - p) * weight
        cov += dp * log_odds
        info += dp * dp / (p * q)
    if variance <= 1e-12:
        return 0.0, 0.0
    lz = (l0 - expected) / math.sqrt(variance)
    if info <= 1e-12:
        return lz, lz
    adjusted = variance - (cov * cov) / info
    if adjusted <= 1e-12:
        return lz, lz
    numerator = (l0 - expected) - cov * score / info
    return lz, numerator / math.sqrt(adjusted)
