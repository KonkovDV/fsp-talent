"""Order inside one category by the confirming test. The list has no name and no account id."""
from __future__ import annotations


def rank_scores(scores: list[float], limit: int = 20) -> dict:
    ordered = sorted(scores, reverse=True)
    return {
        "total": len(ordered),
        "items": [{"place": index, "test": round(score, 2)} for index, score in enumerate(ordered[:limit], start=1)],
    }


def rank_pairs(rows: list[tuple], limit: int = 20) -> dict:
    """(P(pass), θ[, stable key]) rows. P(pass) saturates at 1.0 for a confident pass, so θ breaks the tie.

    RG-06: the order follows the numbers the page shows. Rows are compared by P(pass) rounded to the two
    digits printed in "test", then by θ (shown too), then by the stable key (a participant id that is
    never printed), so equal shown values never fall into a hidden order or into the order of the query plan.
    """
    def key(r: tuple) -> tuple:
        theta = r[1] if r[1] is not None else float("-inf")
        stable = str(r[2]) if len(r) > 2 and r[2] is not None else ""
        return (-round(r[0], 2), -theta, stable)

    ordered = [(r[0], r[1]) for r in sorted(rows, key=key)]
    return {
        "total": len(ordered),
        "items": [{"place": index, "test": round(score, 2),
                   "theta": None if theta is None else round(theta, 2)}
                  for index, (score, theta) in enumerate(ordered[:limit], start=1)],
    }
