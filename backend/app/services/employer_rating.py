"""Company figure from open signals. The registries themselves are not called."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmployerTrustSignals:
    """Fields a caller may fill. The tax id is carried and is not a point in the score."""

    inn: str
    has_otechestvennoe_po: bool
    tender_count: int
    review_score: float
    salary_spread_pct: float


def compute_trust_score(signals: EmployerTrustSignals) -> float:
    """A figure from 0 to 10. Reviews, a registry mark, tenders and a pay gap. Nothing else."""
    score = 3.0
    score += (signals.review_score - 3) * 1.5
    if signals.has_otechestvennoe_po:
        score += 1.0
    score += min(signals.tender_count * 0.3, 1.5)
    score -= max(signals.salary_spread_pct - 5, 0) * 0.6
    return max(0.0, min(10.0, round(score, 1)))
