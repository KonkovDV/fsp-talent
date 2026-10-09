"""A demo company score shown before the candidate accepts. Not a live registry.

The figure starts at 3. Known demo names use a fixed table. Everyone else is a
stable mix of the name. A process tier is not an input and is not shown.
"""
from __future__ import annotations

import hashlib

# reviews 1..5, registry yes/no, tenders 0..20, pay gap of leadership to engineers.
_KNOWN = {
    "сибирский код": {"reviews": 4.2, "registry": True, "tenders": 8, "pay_gap": 3.0},
    "квантовая лаборатория": {"reviews": 3.4, "registry": False, "tenders": 2, "pay_gap": 6.0},
}


def _signals(name: str) -> dict:
    key = name.strip().casefold()
    if key in _KNOWN:
        return _KNOWN[key]
    digest = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16)
    return {
        "reviews": 2.5 + (digest % 26) / 10,
        "registry": digest % 3 == 0,
        "tenders": digest % 21,
        "pay_gap": 2 + (digest % 50) / 10,
    }


def company_score(name: str) -> dict:
    row = _signals(name or "")
    value = 3.0
    value += (float(row["reviews"]) - 3) * 1.5
    if row["registry"]:
        value += 1.0
    value += min(20, int(row["tenders"])) / 20 * 1.5
    gap = float(row["pay_gap"])
    if gap > 5:
        value -= (gap - 5) * 0.6
    value = max(0.0, min(10.0, value))
    if value >= 7.5:
        label = "высокий"
    elif value >= 5:
        label = "средний"
    else:
        label = "низкий"
    return {
        "score": round(value, 1),
        "label": label,
        "demo": True,
        "note": "Демо-таблица, не запрос в живой реестр.",
    }
