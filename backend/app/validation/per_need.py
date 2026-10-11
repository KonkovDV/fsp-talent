"""Per-need breakdown for the public evaluation page: where on the jury's own set the model wins or loses.

The aggregates of ``public_report`` stay as they are. Each need is ranked the same way ``evaluate`` ranks it
(only the labelled candidates of that need), by the product model and by the resume baseline. The paired
difference of nDCG@10 is averaged over needs with at least one relevant candidate, with the same percentile
bootstrap and the same fixed seed as the aggregate interval, so two equal requests give equal numbers.
"""
from __future__ import annotations

import random
import statistics

from app.validation.matching import _relevant, bootstrap_ci, ndcg, precision, rank

TOP = 5
MODEL, RESUME = "full", "keyword"


def _pool(dataset: dict, labels: dict[str, int]) -> dict:
    chosen = set(labels)
    return {"candidates": [c for c in dataset["candidates"] if c["id"] in chosen]}


def per_need(dataset: dict) -> list[dict]:
    """One row per need, in the order the needs came in."""
    rng = random.Random(1)  # unused by the two deterministic orders; kept for the rank() signature
    rows = []
    for need in dataset["needs"]:
        labels = dataset["labels"][need["id"]]
        pool = _pool(dataset, labels)
        model = rank(pool, need, MODEL, rng)
        resume = rank(pool, need, RESUME, rng)
        rows.append({
            "need_id": need["id"],
            "role": need.get("role"), "grade": need.get("grade"),
            "judged": len(labels), "relevant": _relevant(labels),
            "k": min(10, len(labels)),
            "p_at_k_model": round(precision(model, labels), 4),
            "p_at_k_resume": round(precision(resume, labels), 4),
            "ndcg10_model": round(ndcg(model, labels), 4),
            "ndcg10_resume": round(ndcg(resume, labels), 4),
            "top": [{"candidate_id": cid, "label": labels.get(cid, 0)} for cid in model[:TOP]],
        })
    return rows


def paired_delta(rows: list[dict]) -> dict:
    """Mean nDCG@10 «model − resume» over needs with a relevant candidate, 95 % bootstrap interval."""
    deltas = [row["ndcg10_model"] - row["ndcg10_resume"] for row in rows if row["relevant"] > 0]
    if not deltas:
        return {"mean": None, "ci": None, "needs": 0, "model_better": 0, "resume_better": 0}
    low, high = bootstrap_ci(deltas)
    return {
        "mean": round(statistics.mean(deltas), 4), "ci": [round(low, 4), round(high, 4)], "needs": len(deltas),
        "model_better": sum(1 for d in deltas if d > 0), "resume_better": sum(1 for d in deltas if d < 0),
    }
