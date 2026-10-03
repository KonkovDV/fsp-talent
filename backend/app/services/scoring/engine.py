"""
Hybrid scoring engine for FSP Talent.

Math model
----------
For each discipline we maintain a Beta-distributed belief over a candidate’s
“true quality” q ∈ [0, 1].  Every competition result contributes an effective
weight wᵢ and an observed quality qᵢ, computed from:

    qᵢ  = event_quality(place, total, competition_status)   # ∈ [0, 1]
    wᵢ  = event_weight(event_date, team_size, reference_date) # time-decay × team-discount

The posterior mean (“score”) and LCB are derived from a Bayesian update onto a
weak Beta prior (mean = PRIOR_MEAN, strength = PRIOR_STRENGTH):

    N_eff = PRIOR_STRENGTH + Σ wᵢ
    mu    = (PRIOR_STRENGTH × PRIOR_MEAN + Σ wᵢ × qᵢ) / N_eff
    sigma = sqrt(mu (1−mu) / N_eff)  (Beta posterior approximation)
    LCB   = mu − 1.28 × sigma         (90 % one-sided lower bound)

Ranking uses LCB to penalise candidates with few events (high uncertainty)
and reward those with consistent results.

Constants
---------
HALF_LIFE      months until event weight halves (temporal decay)
TOP_N          number of top events considered per discipline
RRF_K          Reciprocal-Rank Fusion constant
PRIOR_STRENGTH pseudo-count of prior observations
PRIOR_MEAN     prior belief of quality for a new candidate
PRIOR_VAR      prior variance (informational only)

Grade thresholds
----------------
LCB thresholds in GRADE_LCB_THRESHOLDS determine which FSP-sport grade a
result set implies.  These are distinct from the HR grade (junior/middle/
senior/lead) which comes from years of experience or declaration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HALF_LIFE: float = 18.0  # months
TOP_N: int = 3            # top events considered per discipline
RRF_K: int = 60           # RRF fusion constant

# Bayesian Beta prior
PRIOR_STRENGTH: float = 2.0    # pseudo-observations
PRIOR_MEAN: float = 0.30       # prior quality belief
PRIOR_VAR: float = 0.04        # prior variance (documentation only)

# EVSK (Event Status Knowledge) weights
_EVSK: dict[str, float] = {
    "world": 1.20,
    "europe": 1.10,
    "russia_championship": 1.00,
    "russia_cup": 0.90,
    "district": 0.70,
    "regional": 0.50,
    "open_online": 0.30,
    "other": 0.20,
}

# Rank ladder thresholds (total_participants required for each FSP rank at 1st place)
_RANK_LADDER: list[tuple[int, str]] = [
    (100, "МСМК"),
    (50,  "МС"),
    (20,  "I"),
    (10,  "II"),
    (0,   "III"),
]

# HR grade thresholds based on FSP-scoring LCB.
# These determine what sport-performance level maps to which HR grade label.
# Distinct from categorization.py grade (which uses years of experience).
GRADE_LCB_THRESHOLDS: dict[str, float] = {
    "lead":   0.85,
    "senior": 0.65,
    "middle": 0.40,
    "junior": 0.00,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class DisciplineScore:
    """Scoring result for a single discipline."""
    discipline: str
    score: float            # Bayesian posterior mean quality ∈ [0, 1]
    lcb: float              # Lower Confidence Bound (90 % one-sided)
    sigma: float            # posterior standard deviation
    confidence: float       # effective weight as fraction of TOP_N (capped at 1)
    fsp_level: str | None   # highest FSP rank achieved (e.g. “МС”, “I”)
    top_event_ids: list[str] = field(default_factory=list)

    @property
    def events_count(self) -> int:  # convenience alias used in tests
        return len(self.top_event_ids)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def percentile(place: int, total: int) -> float:
    """Fraction of competitors outperformed, adjusted for a single-participant field.

    Uses the mid-point convention so that first place in a field of 1 gives 0.5
    (maximum epistemic humility) rather than 1.0.
    """
    if total <= 0:
        return 0.5
    if total == 1:
        return 0.5
    return max(0.0, min(1.0, (total - place) / (total - 1)))


def event_weight(event_date: date, team_size: int, reference_date: date) -> float:
    """Time-decay × team-size discount for a single event.

    Time decay: weight halves every ``HALF_LIFE`` months.
    Team discount: weight is divided by sqrt(team_size) to reflect individual
    contribution uncertainty in larger teams.
    """
    months_ago = (
        (reference_date.year - event_date.year) * 12
        + (reference_date.month - event_date.month)
    )
    decay = 2.0 ** (-max(0, months_ago) / HALF_LIFE)
    team_discount = 1.0 / math.sqrt(max(1, team_size))
    return decay * team_discount


def rank_equivalent(status: str, place: int, total: int) -> str:
    """Infer the FSP sport rank implied by this result."""
    if status not in ("russia_championship", "russia_cup", "world", "europe"):
        # Only national+ results count for rank
        if status == "district":
            # Top-3 at district ⇒ II
            if place <= 3 and total >= 10:
                return "II"
            if place == 1 and total >= 40:
                return "II"
        elif status == "regional":
            if place == 1 and total >= 40:
                return "II"
            if place <= 3 and total >= 10:
                return "III"
        return "III"

    # National/international: check rank_ladder
    for min_total, rank in _RANK_LADDER:
        if place == 1 and total >= min_total:
            return rank
    # Place > 1: step down by place
    base_idx = next(
        (i for i, (t, _) in enumerate(_RANK_LADDER) if total >= t),
        len(_RANK_LADDER) - 1,
    )
    idx = min(base_idx + place - 1, len(_RANK_LADDER) - 1)
    return _RANK_LADDER[idx][1]


def fsp_level_from_rank(rank: str) -> str | None:
    """Map a rank string to a human-readable FSP level label."""
    _map = {
        "МСМК": "elite",
        "МС":   "master",
        "I":    "candidate_master",
        "II":   "first_class",
        "III":  "second_class",
    }
    return _map.get(rank)


def event_quality(place: int, total: int, status: str) -> float:
    """Quality score for a single event: percentile × EVSK weight, capped at 1.0."""
    evsk = _EVSK.get(status, _EVSK["other"])
    return min(1.0, percentile(place, total) * evsk)


def classify_grade(lcb: float) -> str:
    """Classify a candidate into an HR grade based on their FSP-scoring LCB.

    Uses ``GRADE_LCB_THRESHOLDS``:
      - lead   ≥ 0.85
      - senior ≥ 0.65
      - middle ≥ 0.40
      - junior < 0.40

    Note: This is the sport-performance grade, not the experience-based grade
    from ``categorization.py``.  Search results use the sport grade when a
    DisciplineScore is available, otherwise fall back to the experience grade.
    """
    for grade, threshold in GRADE_LCB_THRESHOLDS.items():
        if lcb >= threshold:
            return grade
    return "junior"


# ---------------------------------------------------------------------------
# Core scoring function
# ---------------------------------------------------------------------------

def compute_discipline_score(
    events: Sequence[dict],
    reference_date: date | None = None,
) -> dict:
    """Compute the Bayesian posterior quality score for a discipline.

    Parameters
    ----------
    events:
        List of event dicts with keys:
          - id (str)
          - place (int)
          - total_participants (int)
          - competition_status (str)
          - team_size (int, default 1)
          - event_date (date)
    reference_date:
        Date used as “now” for time-decay (defaults to today).

    Returns
    -------
    dict with keys: score, lcb, sigma, confidence, events_count,
                    fsp_level, top_event_ids.
    """
    ref = reference_date or date.today()

    if not events:
        # Return the prior
        sigma = math.sqrt(PRIOR_MEAN * (1.0 - PRIOR_MEAN) / PRIOR_STRENGTH)
        lcb = PRIOR_MEAN - 1.28 * sigma
        return {
            "score": PRIOR_MEAN,
            "lcb": round(lcb, 6),
            "sigma": round(sigma, 6),
            "confidence": 0.0,
            "events_count": 0,
            "fsp_level": None,
            "top_event_ids": [],
        }

    weighted: list[tuple[float, float, str]] = []  # (weight, quality, event_id)
    for ev in events:
        place = int(ev["place"])
        total = int(ev["total_participants"])
        status = str(ev.get("competition_status", "other"))
        team_size = int(ev.get("team_size", 1))
        event_date = ev["event_date"]
        if not isinstance(event_date, date):
            raise TypeError(f"event_date must be a date, got {type(event_date)}")

        w = event_weight(event_date, team_size, ref)
        q = event_quality(place, total, status)
        weighted.append((w, q, str(ev["id"])))

    # Keep only TOP_N by weight (most recent / solo events)
    weighted.sort(key=lambda x: x[0], reverse=True)
    top = weighted[:TOP_N]

    sum_w = sum(w for w, _, _ in top)
    sum_wq = sum(w * q for w, q, _ in top)

    # Bayesian update
    n_eff = PRIOR_STRENGTH + sum_w
    mu = (PRIOR_STRENGTH * PRIOR_MEAN + sum_wq) / n_eff
    sigma = math.sqrt(mu * (1.0 - mu) / n_eff)
    lcb = mu - 1.28 * sigma

    # FSP level: best rank across all events (not just top)
    best_rank: str | None = None
    _rank_order = ["МСМК", "МС", "I", "II", "III"]
    for ev in events:
        r = rank_equivalent(
            str(ev.get("competition_status", "other")),
            int(ev["place"]),
            int(ev["total_participants"]),
        )
        if best_rank is None or _rank_order.index(r) < _rank_order.index(best_rank):
            best_rank = r

    confidence = min(1.0, sum_w / TOP_N)

    return {
        "score": round(mu, 6),
        "lcb": round(lcb, 6),
        "sigma": round(sigma, 6),
        "confidence": round(confidence, 6),
        "events_count": len(events),
        "fsp_level": best_rank,
        "top_event_ids": [eid for _, _, eid in top],
    }
