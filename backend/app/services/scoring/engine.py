"""
FSP Talent Scoring Engine v2 (deterministic, versioned).

Per event e:
  p_e = 1 - (place - 0.5) / N                      Hazen percentile: defined for N=1, never 0
  rank_e = ЕВСК rank equivalent of (status, place, N)
  q_e = W[rank_e] * p_e                            result quality in (0, 1]
  d_e = 2^(-months / HALF_LIFE_MONTHS)             recency
  w_e = d_e / sqrt(team_size)                      evidence weight: a team result says less about the individual

Per discipline (empirical-Bayes shrinkage to the population prior):
  n_eff = sum(w_e)
  mu    = (sum(w_e * q_e) + K * PRIOR_MEAN) / (n_eff + K)
  sigma = sqrt(PRIOR_VAR / (n_eff + K))
  lcb   = mu - sigma                               ranking key (conservative)

Team results reduce evidence weight (wider sigma) instead of lowering the level.
All constants are expert priors; any change must bump VERSION.
"""
from __future__ import annotations

import math
from datetime import date
from typing import TypedDict

VERSION = "v2.0.0"
HALF_LIFE_MONTHS = 18.0
PRIOR_STRENGTH = 2.0      # K: prior counts as two full-weight events
PRIOR_MEAN = 0.30
PRIOR_VAR = 0.04

RANK_ORDER = ["МС", "КМС", "I", "II", "III", "юн"]
RANK_WEIGHTS: dict[str | None, float] = {
    "МС": 1.00, "КМС": 0.85, "I": 0.70, "II": 0.55, "III": 0.40, "юн": 0.30, None: 0.20,
}

# Simplified ЕВСК ladder: status -> [(max_place, rank)]. Approximation of the norms for
# "спортивное программирование"; must be reconciled with the current order (Минспорт № 299 от 09.04.2026).
EVSK_LADDER: dict[str, list[tuple[int, str]]] = {
    "world":               [(8, "МС"), (16, "КМС"), (32, "I")],
    "russia_championship": [(2, "МС"), (4, "КМС"), (8, "I"), (16, "II"), (32, "III")],
    "russia_cup":          [(1, "МС"), (3, "КМС"), (8, "I"), (16, "II"), (32, "III")],
    "russia_youth":        [(3, "КМС"), (8, "I"), (16, "II"), (32, "III")],
    "all_russian":         [(3, "КМС"), (8, "I"), (16, "II"), (32, "III")],
    "federal_district":    [(3, "I"), (8, "II"), (16, "III")],
    "regional":            [(3, "II"), (8, "III"), (16, "юн")],
    "other":               [(3, "III"), (8, "юн")],
}
MIN_PARTICIPANTS_FOR_MASTER = 6   # МС/КМС require at least 6 competitors

STATUS_LABELS = {
    "world": "Чемпионат/первенство мира",
    "russia_championship": "Чемпионат России",
    "russia_cup": "Кубок России",
    "russia_youth": "Первенство России",
    "all_russian": "Всероссийские соревнования",
    "federal_district": "Соревнования федерального округа",
    "regional": "Соревнования субъекта РФ",
    "other": "Прочие соревнования",
}

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
    best_rank: str | None
    top_event_ids: list[str]
    scoring_version: str


def rank_equivalent(status: str, place: int, total: int) -> str | None:
    for max_place, rank in EVSK_LADDER.get(status, EVSK_LADDER["other"]):
        if place <= max_place:
            if rank in ("МС", "КМС") and total < MIN_PARTICIPANTS_FOR_MASTER:
                return "I"
            return rank
    return None


def rank_at_least(rank: str | None, minimum: str) -> bool:
    return rank is not None and RANK_ORDER.index(rank) <= RANK_ORDER.index(minimum)


def percentile(place: int, total: int) -> float:
    total = max(total, 1)
    place = min(max(place, 1), total)
    return 1.0 - (place - 0.5) / total


def months_between(event_date: date, ref: date) -> float:
    return max(0.0, (ref - event_date).days / 30.4375)


def event_quality(place: int, total: int, status: str) -> float:
    return RANK_WEIGHTS[rank_equivalent(status, place, total)] * percentile(place, total)


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
    n_eff = sum(w for _, w, _ in weighted)
    mu = (sum(q * w for q, w, _ in weighted) + PRIOR_STRENGTH * PRIOR_MEAN) / (n_eff + PRIOR_STRENGTH)
    sigma = math.sqrt(PRIOR_VAR / (n_eff + PRIOR_STRENGTH))
    ranks = [rank_equivalent(e["competition_status"], e["place"], e["total_participants"]) for _, _, e in weighted]
    known = [r for r in ranks if r is not None]
    best_rank = min(known, key=RANK_ORDER.index) if known else None
    top = sorted(weighted, key=lambda t: t[0] * t[1], reverse=True)[:3]
    return DisciplineResult(
        score=round(mu, 4),
        sigma=round(sigma, 4),
        lcb=round(mu - sigma, 4),
        confidence=round(n_eff / (n_eff + PRIOR_STRENGTH), 4),
        events_count=len(events),
        team_events_count=sum(1 for e in events if e["team_size"] > 1),
        best_rank=best_rank,
        top_event_ids=[e["id"] for _, _, e in top],
        scoring_version=VERSION,
    )
