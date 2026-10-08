"""
FSP Talent Scoring Engine v3 (deterministic, versioned).

ФСП (Q&A): every competition counts the same; ranking "чемпионат России выше хакатона" is not advised.
What matters is how many competitions a candidate took part in and how well: winner and prize-winner
versus a plain participant, so that a profile cannot be padded with online participations.

Per event e (competition_status is NOT used):
  class_e = result class from place and field size N        (RESULT_CLASSES, monotone)
            winner (place 1)            1.00   needs N ≥ MIN_FIELD_FOR_PRIZE
            prize-winner (places 2–3)   0.85   needs N ≥ MIN_FIELD_FOR_PRIZE
            top 10 % (place ≤ 0.1·N)    0.65
            top half (place ≤ 0.5·N)    0.45
            other participation         0.00
  q_e = class_e                                    result quality in [0, 1]
  d_e = 2^(-months / HALF_LIFE_MONTHS)             recency
  w_e = d_e / sqrt(team_size)                      evidence weight: a team result says less about the individual

Only the EVENT_CAP strongest events (by q·w) enter the sums. A long list cannot crowd out a few real results.

Per discipline (empirical-Bayes shrinkage to the population prior):
  n_eff = sum(w_e)                                 over the capped events
  mu    = (sum(w_e * q_e) + K * PRIOR_MEAN) / (n_eff + K)
  sigma = sqrt(PRIOR_VAR / (n_eff + K))
  lcb   = mu - sigma                               ranking key (conservative)

A plain participation scores 0. It does not lift the mean, and because a zero still
enters the count it can lower the lower bound. Team results reduce evidence
weight (wider sigma) instead of lowering the level; the team contribution is not separated (Q&A).
The score composition is unchanged in v3.2.0. The rank is not computed here: it is a registry fact
(discipline, rank, assignment date, order number) stored beside the score and it still does not enter it.
All constants are expert priors; any change to the score must bump VERSION.
"""
from __future__ import annotations

import math
from datetime import date
from typing import TypedDict

VERSION = "v3.2.0"
HALF_LIFE_MONTHS = 18.0
PRIOR_STRENGTH = 2.0      # K: prior counts as two full-weight events
PRIOR_MEAN = 0.30
PRIOR_VAR = 0.04
# How many events enter the discipline sum. The rest stay on the profile and do not move the score.
EVENT_CAP = 5

# Result class -> quality. Monotone in the result; the same for every competition status.
RESULT_CLASSES: dict[str, float] = {
    "winner": 1.00, "prize": 0.85, "top10": 0.65, "top50": 0.45, "participant": 0.0,
}
RESULT_CLASS_LABELS = {
    "winner": "победитель", "prize": "призёр", "top10": "в топ-10 %", "top50": "в верхней половине",
    "participant": "участник",
}
# Winning a field of two is not a win: prize classes need a real field, otherwise the share of the field decides.
MIN_FIELD_FOR_PRIZE = 6

# Strongest rank first. Youth ranks stay separate. The product does not invent МСМК: the sport's
# norms do not list it. A rank is never derived from a place; this order is only for the filter.
RANK_ORDER = ["МС", "КМС", "I", "II", "III", "I юн.", "II юн.", "III юн."]

class EventInput(TypedDict):
    id: str
    place: int
    total_participants: int
    competition_status: str
    team_size: int
    event_date: date


class DisciplineResult(TypedDict):
    score: float
    sigma: float
    lcb: float
    confidence: float
    events_count: int
    team_events_count: int
    top_event_ids: list[str]
    scoring_version: str


def rank_at_least(rank: str | None, minimum: str) -> bool:
    return rank is not None and RANK_ORDER.index(rank) <= RANK_ORDER.index(minimum)


def percentile(place: int, total: int) -> float:
    total = max(total, 1)
    place = min(max(place, 1), total)
    return 1.0 - (place - 0.5) / total


def months_between(event_date: date, ref: date) -> float:
    return max(0.0, (ref - event_date).days / 30.4375)


def result_class(place: int, total: int) -> str:
    """Winner / prize-winner / top 10 % / top half / participant, from the place in the event only."""
    total = max(total, 1)
    place = min(max(place, 1), total)
    if total >= MIN_FIELD_FOR_PRIZE and place == 1:
        return "winner"
    if total >= MIN_FIELD_FOR_PRIZE and place <= 3:
        return "prize"
    share = place / total
    if share <= 0.10:
        return "top10"
    if share <= 0.50:
        return "top50"
    return "participant"


def event_quality(place: int, total: int, status: str | None = None) -> float:
    """Result quality. `status` is accepted for old callers and ignored: all competitions weigh the same."""
    return RESULT_CLASSES[result_class(place, total)]


def event_weight(event_date: date, team_size: int, ref: date) -> float:
    decay = 2.0 ** (-months_between(event_date, ref) / HALF_LIFE_MONTHS)
    return decay / math.sqrt(max(team_size, 1))


def compute_discipline_score(events: list[EventInput], reference_date: date | None = None) -> DisciplineResult:
    ref = reference_date or date.today()
    weighted = []
    for e in events:
        q = event_quality(e["place"], e["total_participants"], e["competition_status"])
        w = event_weight(e["event_date"], e["team_size"], ref)
        weighted.append((q, w, e))
    ranked = sorted(weighted, key=lambda t: (t[0] * t[1], t[1]), reverse=True)[:EVENT_CAP]
    n_eff = sum(w for _, w, _ in ranked)
    mu = (sum(q * w for q, w, _ in ranked) + PRIOR_STRENGTH * PRIOR_MEAN) / (n_eff + PRIOR_STRENGTH)
    sigma = math.sqrt(PRIOR_VAR / (n_eff + PRIOR_STRENGTH))
    top = ranked[:3]
    return DisciplineResult(
        score=round(mu, 4),
        sigma=round(sigma, 4),
        lcb=round(mu - sigma, 4),
        confidence=round(n_eff / (n_eff + PRIOR_STRENGTH), 4),
        events_count=len(events),
        team_events_count=sum(1 for e in events if e["team_size"] > 1),
        top_event_ids=[e["id"] for _, _, e in top],
        scoring_version=VERSION,
    )
