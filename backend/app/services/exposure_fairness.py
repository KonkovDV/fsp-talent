"""Who reaches the top slice, grouped by a label that is not a score input.

Region stays outside the match. This report only compares selection rates.
A group smaller than five people is not compared. The floor is four fifths.
"""
from __future__ import annotations

import math

FLOOR = 0.8
MIN_GROUP = 5


def mark_top(rows: list[tuple[str, float, int]], keep: int) -> list[tuple[str, bool]]:
    """Mark the keep highest scores. The third value breaks ties and is not the region."""
    order = sorted(range(len(rows)), key=lambda i: (-rows[i][1], rows[i][2], i))
    chosen = set(order[: max(0, keep)])
    return [(rows[i][0], i in chosen) for i in range(len(rows))]


def impact_report(rows: list[tuple[str, bool]]) -> dict:
    buckets: dict[str, list[bool]] = {}
    for label, selected in rows:
        buckets.setdefault(label or "не указан", []).append(bool(selected))
    groups = []
    for label, flags in sorted(buckets.items()):
        n = len(flags)
        k = sum(1 for flag in flags if flag)
        groups.append({"region": label, "selected": k, "n": n, "rate": round(k / n, 3) if n else 0.0})
    usable = [group for group in groups if group["n"] >= MIN_GROUP]
    if len(usable) < 2:
        return {"groups": groups, "min_ratio": None, "clears": True, "floor": FLOOR,
                "note": "Мало групп для сравнения. Регион в балл не входит."}
    best = max(group["rate"] for group in usable)
    if best <= 0:
        return {"groups": groups, "min_ratio": 1.0, "clears": True, "floor": FLOOR,
                "note": "В верхний срез никто не попал. Регион в балл не входит."}
    ratios = []
    for group in usable:
        ratio = group["rate"] / best
        group["ratio"] = round(ratio, 3)
        ratios.append(ratio)
    lowest = min(ratios)
    return {
        "groups": groups,
        "min_ratio": round(lowest, 3),
        "clears": lowest + 1e-9 >= FLOOR,
        "floor": FLOOR,
        "note": "Отношение доли попадания в верхний срез к самой высокой доле. Регион в балл не входит.",
    }


def skew_at_k(ranked_labels: list[str], pool_labels: list[str], label: str, k: int) -> float | None:
    """Skew@k of Geyik et al. (KDD 2019, doi:10.1145/3292500.3330691).

    ln(share of the label in the top k / share of the label in the pool). Zero means the top k mirrors the
    pool; −0.22 is about a fifth fewer than the pool share. None when the label is absent from the pool or
    from the top k (the logarithm is undefined there).
    """
    top = ranked_labels[: max(0, k)]
    if not top or not pool_labels:
        return None
    in_pool = sum(1 for value in pool_labels if value == label) / len(pool_labels)
    in_top = sum(1 for value in top if value == label) / len(top)
    if in_pool <= 0 or in_top <= 0:
        return None
    return math.log(in_top / in_pool)
