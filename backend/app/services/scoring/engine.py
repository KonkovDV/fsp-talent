"""
FSP Talent Scoring Engine v4.2.0 (deterministic, versioned).

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

Only events with a result (q > 0) enter the score. A plain participation is counted on the
profile (events_count) and never enters the sums: it can neither lift nor lower the score.

The score is the best lower bound over subsets of at most EVENT_CAP result events (exhaustive
search, the empty subset is the baseline):
  n_eff = sum(w_e)                                 over the chosen events
  mu    = (sum(w_e * q_e) + K * PRIOR_MEAN) / (n_eff + K)
  sigma = sqrt(PRIOR_VAR / (n_eff + K))
  lcb   = max over subsets (mu - sigma)            ranking key (conservative)

Monotonicity (v4.2.0): adding any event never lowers lcb, and no history at all is
the floor (LCB0). The monthly cap and the long-history limit are constraints on the chosen subset,
not a pre-filter that drops a heavy result because a lighter one has a higher class. v4.1.0 sorted
each month by quality first and could replace a prize in a large field with a win in a tiny one,
so a new honest result lowered the bound. The v3 rule took the five strongest events by q·w
including zeros, so a plain participation could push the bound below an empty history. Team results
reduce evidence weight (wider sigma) instead of lowering the level; the team contribution is not
separated (Q&A).
The rank is not computed here: it is a registry fact stored beside the score and does not enter it.
The reference date must be the same for everyone compared: callers pass it explicitly
(services.profile.scoring_reference_date); the date.today() default is kept for old callers only.
All constants are expert priors; any change to the score must bump VERSION.
"""
from __future__ import annotations

import math
from datetime import date
from itertools import combinations
from typing import TypedDict

VERSION = "v4.2.0"
HALF_LIFE_MONTHS = 18.0
PRIOR_STRENGTH = 2.0      # K: prior counts as two full-weight events
PRIOR_MEAN = 0.30
PRIOR_VAR = 0.04
# How many events a subset may contain. The rest stay on the profile. The bound uses the best subset.
EVENT_CAP = 5
# Size at which the greedy subset matches the exhaustive one in tests. The product search is
# best_subset_month_capped and does not cut the pool down to this size.
EXACT_SUBSET_LIMIT = 16

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
# Evidence from a field of N people weighs 1 − e^(−N/FIELD_SCALE): a place among 6 is about a fifth
# of a place among 200. Combined with EVENT_CAP this bounds what any number of small fields can add.
FIELD_SCALE = 30.0
# A chosen subset holds at most this many results from one calendar month.
# The search still sees every result that month. Cutting to the highest classes first is not monotone.
PER_MONTH_CAP = 2

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


def field_weight(total: int | None) -> float:
    if not total:
        return 1.0
    return 1.0 - math.exp(-max(int(total), 1) / FIELD_SCALE)


def event_weight(event_date: date, team_size: int, ref: date, total: int | None = None) -> float:
    decay = 2.0 ** (-months_between(event_date, ref) / HALF_LIFE_MONTHS)
    return decay / math.sqrt(max(team_size, 1)) * field_weight(total)


def posterior(pairs: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Mean, sigma and lower bound of one subset. pairs are (quality, weight)."""
    n_eff = sum(w for _, w in pairs)
    mu = (sum(q * w for q, w in pairs) + PRIOR_STRENGTH * PRIOR_MEAN) / (n_eff + PRIOR_STRENGTH)
    sigma = math.sqrt(PRIOR_VAR / (n_eff + PRIOR_STRENGTH))
    return mu, sigma, mu - sigma


# Empty history: μ0 − σ0/√K. A subset is kept only when it beats this.
LCB0 = PRIOR_MEAN - math.sqrt(PRIOR_VAR / PRIOR_STRENGTH)


def _lcb(chosen: list[tuple[float, float, EventInput]]) -> float:
    return posterior([(q, w) for q, w, _ in chosen])[2]


def _month_key(event: EventInput) -> tuple[int, int]:
    when = event["event_date"]
    return when.year, when.month


def best_subset_month_capped(weighted: list[tuple[float, float, EventInput]]) -> list[tuple[float, float, EventInput]]:
    """Best subset of at most EVENT_CAP events, with at most PER_MONTH_CAP from one calendar month.

    The search sees every result event. A cap that first throws events away by quality is not monotone:
    a new high class with a tiny weight can evict a heavier result and lower the bound.
    """
    best: list[tuple[float, float, EventInput]] = []
    best_lcb = _lcb(best)
    by_month: dict[tuple[int, int], list[tuple[float, float, EventInput]]] = {}
    for item in weighted:
        by_month.setdefault(_month_key(item[2]), []).append(item)
    options: list[list[list[tuple[float, float, EventInput]]]] = []
    for items in by_month.values():
        choices: list[list[tuple[float, float, EventInput]]] = [[]]
        choices.extend([item] for item in items)
        if PER_MONTH_CAP >= 2:
            choices.extend(list(pair) for pair in combinations(items, 2))
        options.append(choices)

    def walk(month: int, chosen: list[tuple[float, float, EventInput]]) -> None:
        nonlocal best, best_lcb
        if month == len(options):
            lcb = _lcb(chosen)
            if lcb > best_lcb + 1e-12:
                best, best_lcb = list(chosen), lcb
            return
        room = EVENT_CAP - len(chosen)
        for choice in options[month]:
            if len(choice) > room:
                continue
            if not choice:
                walk(month + 1, chosen)
                continue
            chosen.extend(choice)
            walk(month + 1, chosen)
            del chosen[-len(choice):]

    if options:
        walk(0, [])
    return best


def best_subset_exact(weighted: list[tuple[float, float, EventInput]]) -> list[tuple[float, float, EventInput]]:
    """Every subset of size at most EVENT_CAP. The empty subset is the baseline."""
    best: list[tuple[float, float, EventInput]] = []
    best_lcb = _lcb(best)
    limit = min(EVENT_CAP, len(weighted))
    for size in range(1, limit + 1):
        for combo in combinations(range(len(weighted)), size):
            chosen = [weighted[i] for i in combo]
            lcb = _lcb(chosen)
            if lcb > best_lcb + 1e-12:
                best, best_lcb = chosen, lcb
    return best


def best_subset_greedy(weighted: list[tuple[float, float, EventInput]]) -> list[tuple[float, float, EventInput]]:
    """Prefixes of the q·w order, then add, drop or swap an event when that raises the bound.

    On lists of at most EXACT_SUBSET_LIMIT events this matches the exhaustive search.
    """
    ranked = sorted(weighted, key=lambda t: (t[0] * t[1], t[1]), reverse=True)
    best: list[tuple[float, float, EventInput]] = []
    best_lcb = _lcb(best)
    prefix: list[tuple[float, float, EventInput]] = []
    for item in ranked[:EVENT_CAP]:
        prefix.append(item)
        lcb = _lcb(prefix)
        if lcb > best_lcb + 1e-12:
            best, best_lcb = list(prefix), lcb
    current = list(best)
    improved = True
    while improved:
        improved = False
        if len(current) < EVENT_CAP:
            for item in ranked:
                if any(item is other or item == other for other in current):
                    continue
                trial = current + [item]
                lcb = _lcb(trial)
                if lcb > best_lcb + 1e-12:
                    current, best, best_lcb = trial, list(trial), lcb
                    improved = True
                    break
        if improved:
            continue
        for i in range(len(current)):
            trial = current[:i] + current[i + 1:]
            lcb = _lcb(trial)
            if lcb > best_lcb + 1e-12:
                current, best, best_lcb = trial, list(trial), lcb
                improved = True
                break
        if improved:
            continue
        for i in range(len(current)):
            for item in ranked:
                if any(item is other or item == other for other in current):
                    continue
                trial = current[:i] + [item] + current[i + 1:]
                lcb = _lcb(trial)
                if lcb > best_lcb + 1e-12:
                    current, best, best_lcb = trial, list(trial), lcb
                    improved = True
                    break
            if improved:
                break
    return best


def _result_pool(events: list[EventInput], ref: date) -> list[tuple[float, float, EventInput]]:
    """(q, w, event) for events with a result. Participations (q = 0) never enter the score."""
    pool = []
    for e in events:
        q = event_quality(e["place"], e["total_participants"], e["competition_status"])
        if q <= 0:
            continue
        pool.append((q, event_weight(e["event_date"], e["team_size"], ref, e["total_participants"]), e))
    return pool


def compute_discipline_score(events: list[EventInput], reference_date: date | None = None) -> DisciplineResult:
    """Best-subset lower bound over result events. Monotone: an added event never lowers lcb."""
    ref = reference_date or date.today()
    chosen = best_subset_month_capped(_result_pool(events, ref))
    mu, sigma, lcb = posterior([(q, w) for q, w, _ in chosen])
    n_eff = sum(w for _, w, _ in chosen)
    top = sorted(chosen, key=lambda t: (t[0] * t[1], t[1]), reverse=True)[:3]
    return DisciplineResult(
        score=round(mu, 4),
        sigma=round(sigma, 4),
        lcb=round(lcb, 4),
        confidence=round(n_eff / (n_eff + PRIOR_STRENGTH), 4) if events else 0.0,
        events_count=len(events),
        team_events_count=sum(1 for e in events if e["team_size"] > 1),
        top_event_ids=[e["id"] for _, _, e in top],
        scoring_version=VERSION,
    )


def lcb_star(events: list[EventInput], reference_date: date | None = None) -> DisciplineResult:
    """Alias kept for the validation scripts: since v4.0.0 the shipped score is the best-subset bound."""
    return compute_discipline_score(events, reference_date)
