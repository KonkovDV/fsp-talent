"""Order inside one category by the confirming test. The list has no name and no account id."""
from __future__ import annotations


def rank_scores(scores: list[float], limit: int = 20) -> dict:
    ordered = sorted(scores, reverse=True)
    return {
        "total": len(ordered),
        "items": [{"place": index, "test": round(score, 2)} for index, score in enumerate(ordered[:limit], start=1)],
    }
