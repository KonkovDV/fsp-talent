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
            other participation         0.25
  q_e = class_e                                    result quality in (0, 1]
  d_e = 2^(-months / HALF_LIFE_MONTHS)             recency
  w_e = d_e / sqrt(team_size)                      evidence weight: a team result says less about the individual

Per discipline (empirical-Bayes shrinkage to the population prior):
  n_eff = sum(w_e)
  mu    = (sum(w_e * q_e) + K * PRIOR_MEAN) / (n_eff + K)
  sigma = sqrt(PRIOR_VAR / (n_eff + K))
  lcb   = mu - sigma                               ranking key (conservative)

Padding does not pay: a participation-only result (0.25) sits below the prior mean (0.30), so many of them
pull mu down while they narrow sigma; a few wins keep a higher lower bound. Team results reduce evidence
weight (wider sigma) instead of lowering the level; the team contribution is not separated (Q&A).
The ЕВСК rank equivalent (МС, КМС, …) is display information only (profile, credential, employer filter)
and does not enter the score. All constants are expert priors; any change must bump VERSION.
"""
from __future__ import annotations

import math
from datetime import date
from typing import TypedDict

VERSION = "v3.0.0"
HALF_LIFE_MONTHS = 18.0
PRIOR_STRENGTH = 2.0      # K: prior counts as two full-weight events
PRIOR_MEAN = 0.30
PRIOR_VAR = 0.04

# Result class -> quality. Monotone in the result; the same for every competition status.
RESULT_CLASSES: dict[str, float] = {
    "winner": 1.00, "prize": 0.85, "top10": 0.65, "top50": 0.45, "participant": 0.25,
}
RESULT_CLASS_LABELS = {
    "winner": "победитель", "prize": "призёр", "top10": "в топ-10 %", "top50": "в верхней половине",
    "participant": "участник",
}
# Winning a field of two is not a win: prize classes need a real field, otherwise the share of the field decides.
MIN_FIELD_FOR_PRIZE = 6

# Display only: the ЕВСК rank equivalent is shown and can be filtered on, it is not part of the score.
RANK_ORDER = ["МС", "КМС", "I", "II", "III", "юн"]

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
