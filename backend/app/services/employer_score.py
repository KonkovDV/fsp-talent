"""A demo company score shown before the candidate accepts. Not a live registry.

Known demo names use a fixed table. Everyone else is a stable mix of the name.
The number is compute_trust_score. A process tier is not an input and is not shown.
"""
from __future__ import annotations

import hashlib

from app.services.employer_rating import EmployerTrustSignals, compute_trust_score

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
    value = compute_trust_score(EmployerTrustSignals(
        inn="",
        has_otechestvennoe_po=bool(row["registry"]),
        tender_count=int(row["tenders"]),
        review_score=float(row["reviews"]),
        salary_spread_pct=float(row["pay_gap"]),
    ))
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
