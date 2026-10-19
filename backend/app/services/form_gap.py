"""Residual gap between leakable wordings and fresh parametric items.

Concept items share a finite wording. Code items are a new instance each time.
If the ability estimate includes the concept items, a leaked wording pulls the
estimate up and hides its own residual. The reference ability is therefore the
posterior from the code items alone, and both residuals are read at that anchor.
A large positive gap is a reason to look at the session. It is not a finding
that the person cheated, and it does not move the grade or the match score.
"""
from __future__ import annotations

from app.services.cat import Response, p3, posterior

FORM_MIN = 3
FORM_GAP = 0.40


def form_gap(rows, theta: float | None = None, *, prior_mean: float = 0.0) -> dict | None:
    """Mean residual by form, anchored on the code-only ability estimate."""
    picked: dict[str, list] = {"concept": [], "code": []}
    for row in rows:
        kind = getattr(row, "kind", None)
        correct = getattr(row, "is_correct", getattr(row, "correct", None))
        if kind not in picked or correct is None:
            continue
        picked[kind].append((row, bool(correct)))
    if len(picked["concept"]) < FORM_MIN or len(picked["code"]) < FORM_MIN:
        return None
    code_responses = [Response(row.a, row.b, row.c, ok) for row, ok in picked["code"]]
    anchor = posterior(code_responses, prior_mean=prior_mean).theta if code_responses else (theta or 0.0)

    def _mean_residual(items: list) -> float:
        total = 0.0
        for row, ok in items:
            p = min(max(p3(anchor, row.a, row.b, row.c), 1e-6), 1.0 - 1e-6)
            total += (1.0 if ok else 0.0) - p
        return total / len(items)

    concept = _mean_residual(picked["concept"])
    code = _mean_residual(picked["code"])
    gap = concept - code
    return {
        "anchor_theta": round(anchor, 3),
        "concept_residual": round(concept, 3),
        "code_residual": round(code, 3),
        "gap": round(gap, 3),
        "concept_n": len(picked["concept"]),
        "code_n": len(picked["code"]),
        "review": gap >= FORM_GAP,
    }
