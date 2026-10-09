"""Leak monitoring by drift of the solve rate.

For every item key we accumulate, over completed sessions, the observed number of right answers and the
number the model expects given the candidate's final ability estimate:

    expected = Σ P(θ̂_session),   variance = Σ P (1 − P),   z = (observed − expected) / sqrt(variance)

A leaked item (or a published solver for a family) is answered right far more often than the ability of the
people answering predicts, so z grows with every session. A key with at least MIN_N answers and z ≥ Z_ALARM
is quarantined: it is no longer served and its answers are dropped when sessions are scored. Ability is
estimated from the whole session, so one leaked key moves θ̂ only a little and the residual stays visible.
A key can be returned to service after review (status back to active, counters reset).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MIN_N = 30
Z_ALARM = 3.5
# One-sided CUSUM on the excess of right answers over the model. A second signal next to z:
# the running sum forgets nothing until it crosses the threshold, so a slow leak shows up.
CUSUM_K = 0.12
CUSUM_H = 7.0


@dataclass
class KeyStats:
    n: int = 0
    correct: int = 0
    expected: float = 0.0
    variance: float = 0.0
    cusum: float = 0.0

    def add(self, p: float, correct: bool) -> None:
        self.n += 1
        self.correct += int(correct)
        self.expected += p
        self.variance += p * (1.0 - p)
        self.cusum = max(0.0, self.cusum + (int(correct) - p - CUSUM_K))

    @property
    def z(self) -> float:
        if self.variance <= 0:
            return 0.0
        return (self.correct - self.expected) / math.sqrt(self.variance)

    @property
    def alarm(self) -> bool:
        return self.n >= MIN_N and self.z >= Z_ALARM

    @property
    def cusum_alarm(self) -> bool:
        return self.n >= MIN_N and self.cusum >= CUSUM_H


def drift_z(n: int, correct: int, expected: float, variance: float) -> float:
    return KeyStats(n, correct, expected, variance).z


def is_alarm(n: int, correct: int, expected: float, variance: float) -> bool:
    return KeyStats(n, correct, expected, variance).alarm


def one_sided_p(z: float) -> float:
    """Upper tail of a standard normal: P(Z ≥ z). The drift statistic is already one-sided."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def bh_reject(p_values: list[float], alpha: float = 0.05) -> list[bool]:
    """Benjamini–Hochberg step-up. True means that null is rejected at the given alpha.

    Sort the p-values and take the largest rank k with p(k) ≤ (k / m) · alpha.
    Every p-value at or below that p(k) is rejected. An empty list rejects nothing.

    The product does not call this. A key is quarantined when its own z reaches
    Z_ALARM or its CUSUM reaches CUSUM_H. Feeding this threshold into that decision
    would change which keys are served, and that change has not been measured.
    Repeated looks at the same key (alpha spending over time) are not applied either.
    """
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    m = len(p_values)
    rejected = [False] * m
    if m == 0:
        return rejected
    order = sorted(range(m), key=lambda i: p_values[i])
    cutoff: float | None = None
    for rank, index in enumerate(order, start=1):
        p = p_values[index]
        if p != p or p < 0.0 or p > 1.0:
            raise ValueError("p-value out of range")
        if p <= (rank / m) * alpha:
            cutoff = p
    if cutoff is None:
        return rejected
    for index, p in enumerate(p_values):
        rejected[index] = p <= cutoff
    return rejected


def leave_family_out(rows: list[tuple[str, str, float, float, float, bool]], prior_mean: float
                     ) -> list[tuple[str, float, bool]]:
    """Model-expected P(correct) for each answered item, with ability estimated WITHOUT the item's family.

    rows: (item_key, family_id, a, b, c, correct). If a whole family leaks, its right answers inflate the
    session's ability estimate and hide the residual; estimating ability from the other families keeps it
    visible. Returns (item_key, p, correct).
    """
    from app.services.cat import Response, p3, posterior

    out = []
    for fam in {r[1] for r in rows}:
        others = [Response(a, b, c, ok) for _, f, a, b, c, ok in rows if f != fam]
        theta = posterior(others, prior_mean=prior_mean).theta
        out += [(key, p3(theta, a, b, c), ok) for key, f, a, b, c, ok in rows if f == fam]
    return out


def calibrate_offset(rows: list[tuple[float, float, float, float, bool]], prior_sd: float = 0.5) -> float:
    """MAP shift δ of an item key's difficulty from answers (theta, a, b, c, correct); prior δ ~ N(0, prior_sd²)."""
    from app.services.cat import p3

    delta = 0.0
    for _ in range(30):
        grad, hess = -delta / prior_sd ** 2, -1.0 / prior_sd ** 2
        for theta, a, b, c, ok in rows:
            p = min(max(p3(theta, a, b + delta, c), 1e-6), 1 - 1e-6)
            star = (p - c) / (1 - c)                        # logistic part
            dp = -a * (1 - c) * star * (1 - star)           # dP/dδ
            grad += dp * ((1 if ok else 0) - p) / (p * (1 - p))
            hess -= dp * dp / (p * (1 - p))
        step = grad / hess
        delta -= step
        if abs(step) < 1e-6:
            break
    return max(-1.5, min(1.5, delta))


def calibrate_discrimination(rows: list[tuple[float, float, float, bool]], a0: float = 1.4,
                             prior_sd: float = 0.35) -> float:
    """MAP of item discrimination on the log scale. rows: (theta, b, c, correct).

    Each row plugs in a point estimate of ability (leave-family-out θ̂), not a posterior
    over θ. This is a Newton step on that fixed θ̂, with a normal prior on log a around
    log(a0). It is not an M-step of marginal maximum likelihood.
    """
    from app.services.cat import p3

    mu = math.log(a0)
    u = mu
    for _ in range(30):
        a = math.exp(u)
        grad = -(u - mu) / prior_sd ** 2
        hess = -1.0 / prior_sd ** 2
        for theta, b, c, ok in rows:
            p = min(max(p3(theta, a, b, c), 1e-6), 1 - 1e-6)
            star = (p - c) / (1.0 - c)
            dp_du = (1.0 - c) * star * (1.0 - star) * (theta - b) * a
            grad += dp_du * ((1 if ok else 0) - p) / (p * (1.0 - p))
            hess -= dp_du * dp_du / (p * (1.0 - p))
        if hess >= -1e-9:
            break
        step = grad / hess
        u = max(math.log(0.2), min(math.log(3.0), u - step))
        if abs(step) < 1e-5:
            break
    return math.exp(u)
