"""Information of the item bank at the grade cuts, and exposure rolled up by family.

The page and the public endpoint show parameters and counts. They do not show stems or right answers.
"""
from __future__ import annotations

import math

from app.items.hierarchy import parent
from app.items.registry import BLUEPRINTS, FAMILIES, expected_guess, families_for
from app.services.cat import CUTS, RANDOMESQUE, info3

# Twelve items is inside the real test (8–20) and long enough for the SE illustration.
ILLUSTRATIVE_ITEMS = 12


def bank_curve(spec: str) -> dict:
    """Best-item Fisher information along the ability scale, and at each grade cut."""
    if spec not in BLUEPRINTS:
        raise ValueError(spec)
    families = families_for(spec)
    curve = []
    for i in range(25):
        theta = round(-3.0 + i * 0.25, 2)
        curve.append({"theta": theta, "information": round(_best(spec, families, theta), 3)})
    cuts = []
    for grade, cut in CUTS.items():
        info = _best(spec, families, cut)
        se = 1.0 / math.sqrt(ILLUSTRATIVE_ITEMS * info) if info > 0 else None
        cuts.append({
            "grade": grade,
            "cut": cut,
            "information": round(info, 3),
            "se_after_12": round(se, 3) if se is not None else None,
        })
    return {
        "spec": spec, "randomesque": RANDOMESQUE, "curve": curve, "cuts": cuts,
        "parents": _parents(spec, families),
    }


def _parents(spec: str, families) -> list[dict]:
    """One row per family: the prior a, and the difficulty of each level. No stems."""
    rows = []
    for fam in families:
        levels = [level for level in fam.levels if fam.available(spec, level)]
        if not levels:
            continue
        rows.append({
            "family_id": fam.id,
            "title": fam.title,
            "a": parent(fam, levels[0])[0],
            "levels": [{"level": level, "b": parent(fam, level)[1]} for level in levels],
        })
    return rows


def _best(spec: str, families, theta: float) -> float:
    best = 0.0
    for fam in families:
        for level in fam.levels:
            if not fam.available(spec, level):
                continue
            a, b = parent(fam, level)
            best = max(best, info3(theta, a, b, expected_guess(fam.id, level)))
    return best


def summarize_exposure(rows: list[tuple[str, int, int, float, str]]) -> dict:
    """Roll item-stat rows up by family. rows: family_id, level, n, cusum, status.

    max_share is the hottest single key divided by all answers. The key itself is not returned.
    """
    total = sum(n for _, _, n, _, _ in rows)
    by: dict[str, dict] = {}
    hottest = 0
    for fam, _level, n, cusum, status in rows:
        title = FAMILIES[fam].title if fam in FAMILIES else fam
        cell = by.setdefault(fam, {
            "family_id": fam, "title": title, "answers": 0, "cusum": 0.0, "quarantined": 0, "max_key": 0,
        })
        cell["answers"] += n
        cell["cusum"] += float(cusum)
        cell["max_key"] = max(cell["max_key"], n)
        hottest = max(hottest, n)
        if status != "active":
            cell["quarantined"] += 1
    families = []
    for cell in by.values():
        shown = cell.pop("max_key")
        cell["cusum"] = round(cell["cusum"], 2)
        cell["max_share"] = round(shown / total, 3) if total else 0.0
        families.append(cell)
    families.sort(key=lambda cell: (-cell["answers"], cell["family_id"]))
    return {
        "answers": total,
        "max_share": round(hottest / total, 3) if total else 0.0,
        "families": families,
    }
