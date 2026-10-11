"""Order inside one category by the confirming test. The list has no name and no account id."""
from __future__ import annotations


def rank_scores(scores: list[float], limit: int = 20) -> dict:
    ordered = sorted(scores, reverse=True)
    return {
        "total": len(ordered),
        "items": [{"place": index, "test": round(score, 2)} for index, score in enumerate(ordered[:limit], start=1)],
    }


def rank_pairs(rows: list[tuple[float, float | None]], limit: int = 20) -> dict:
    """(P(pass), θ) pairs. P(pass) saturates at 1.0 for a confident pass, so θ breaks the tie and is shown."""
    ordered = sorted(rows, key=lambda r: (r[0], r[1] if r[1] is not None else float("-inf")), reverse=True)
    return {
        "total": len(ordered),
        "items": [{"place": index, "test": round(score, 2),
                   "theta": None if theta is None else round(theta, 2)}
                  for index, (score, theta) in enumerate(ordered[:limit], start=1)],
    }
