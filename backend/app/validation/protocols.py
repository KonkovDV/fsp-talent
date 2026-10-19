"""Matching under two published graded protocols: `python -m app.validation.protocols --protocol a|b`.

Same synthetic world and the same product order as `app.validation.matching`; only the relevance rubric over the
hidden truth, the need filter and the metric definitions follow two published methods.
The product scorer and its weights are not changed and nothing is fitted on these seeds.

Protocol A (graded 0..3, rubric by role, grade distance, coverage of required skills, position inside the grade):
  0  other role, real grade two or more steps away, or none of the required skills is real
  1  adjacent grade, or less than 1/3 of the required skills are real
  2  requested grade with acceptable skills, or one step ABOVE the request with at least 1/3 of the skills
  3  requested grade, at least 2/3 of the required skills are real and θ in the upper half of the grade band
  −1 if the candidate's work format does not intersect the need's (salary is not modelled in our world).
  Needs with fewer than three candidates labelled ≥ 2 are skipped.
Protocol B (utility rubric): u = role_fit·grade_fit·(0.25 + 0.75·coverage)·ability, role_fit 1 / 0.4 adjacent,
  grade_fit 1 same / 0.75 one above / 0.45 one below / 0 else, ability 0.85 + 0.3·min(1, θ − cut) inside the
  requested grade; label 3 if u ≥ 0.8, 2 if ≥ 0.6, 1 if ≥ 0.4. Needs with no candidate labelled ≥ 2 are skipped.
Both: nDCG@10 with gain 2^rel − 1 and the ideal over the whole labelled pool, P@10 (rel ≥ 2, ten seats),
MRR (reciprocal rank of the first rel ≥ 2). The strict table of `app.validation.matching` is printed beside.
"""
from __future__ import annotations

import argparse
import random
import statistics

from app.services.matching import GRADES, ROLE_NEIGHBOURS
from app.validation.matching import CUTS, HOLDOUT_SEEDS, bootstrap_ci, make_dataset, ndcg, rank

PUBLIC_SEEDS = (2026, 2027, 2028)


def _band(grade: str) -> tuple[float, float]:
    lo = CUTS[grade]
    i = GRADES.index(grade)
    hi = CUTS[GRADES[i + 1]] if i + 1 < len(GRADES) else lo + 1.0
    return lo, hi


def label_a(need: dict, cand: dict) -> int:
    t, o = cand["truth"], cand["observed"]
    if t["role"] != need["role"]:
        return 0
    tg, ng = GRADES.index(t["grade"]), GRADES.index(need["grade"])
    dist = abs(tg - ng)
    if dist >= 2:
        return 0
    req = need["skills"]
    cov = sum(1 for s in req if s in t["skills"]) / len(req) if req else 1.0
    if cov == 0:
        return 0
    if dist == 1 and tg > ng and cov >= 0.34:
        rel = 2
    elif dist == 1 or cov < 0.34:
        rel = 1
    else:
        rel = 2
        lo, hi = _band(t["grade"])
        if cov >= 0.66 and t["theta"] >= (lo + hi) / 2:
            rel = 3
    fmt = need.get("work_format")
    if fmt and o.get("work_formats") and fmt not in o["work_formats"]:
        rel -= 1
    return max(0, rel)


def label_b(need: dict, cand: dict) -> int:
    t = cand["truth"]
    if t["role"] == need["role"]:
        role_fit = 1.0
    elif t["role"] in ROLE_NEIGHBOURS.get(need["role"], set()):
        role_fit = 0.4
    else:
        return 0
    d = GRADES.index(t["grade"]) - GRADES.index(need["grade"])
    grade_fit = {0: 1.0, 1: 0.75, -1: 0.45}.get(d, 0.0)
    req = need["skills"]
    cov = sum(1 for s in req if s in t["skills"]) / len(req) if req else 1.0
    ability = 0.85 + 0.3 * min(1.0, t["theta"] - CUTS[t["grade"]]) if d == 0 else 1.0
    u = role_fit * grade_fit * (0.25 + 0.75 * cov) * ability
    return 3 if u >= 0.8 else 2 if u >= 0.6 else 1 if u >= 0.4 else 0


PROTOCOLS = {"a": (label_a, 3), "b": (label_b, 1)}


def precision10(ranked: list[str], labels: dict[str, int], k: int = 10) -> float:
    return sum(1 for cid in ranked[:k] if labels.get(cid, 0) >= 2) / k


def mrr(ranked: list[str], labels: dict[str, int]) -> float:
    return next((1.0 / (i + 1) for i, cid in enumerate(ranked) if labels.get(cid, 0) >= 2), 0.0)


def run_seed(seed: int, protocol: str, method: str = "full", n_candidates: int = 800, n_needs: int = 80,
             clean: bool = False) -> dict:
    data = make_dataset(n_candidates, n_needs, seed, clean=clean)
    by_id = {c["id"]: c for c in data["candidates"]}
    rng = random.Random(seed)
    out = {"ndcg": [], "p10": [], "mrr": [], "skipped": 0}
    for need in data["needs"]:
        if protocol == "strict":
            labels, min_rel = data["labels"][need["id"]], 1
        else:
            fn, min_rel = PROTOCOLS[protocol]
            labels = {cid: fn(need, c) for cid, c in by_id.items()}
        if sum(1 for v in labels.values() if v >= 2) < min_rel:
            out["skipped"] += 1
            continue
        ranked = rank(data, need, method, rng)
        out["ndcg"].append(ndcg(ranked, labels))
        out["p10"].append(precision10(ranked, labels))
        out["mrr"].append(mrr(ranked, labels))
    return out


def summary(seeds: tuple[int, ...], protocol: str, method: str = "full", clean: bool = False) -> dict:
    pooled = {"ndcg": [], "p10": [], "mrr": []}
    per_seed, skipped = {}, 0
    for sd in seeds:
        r = run_seed(sd, protocol, method, clean=clean)
        skipped += r["skipped"]
        per_seed[sd] = round(statistics.mean(r["ndcg"]), 3)
        for k in pooled:
            pooled[k] += r[k]
    res = {k: (statistics.mean(v), *bootstrap_ci(v)) for k, v in pooled.items()}
    return {"metrics": res, "needs": len(pooled["ndcg"]), "skipped": skipped, "per_seed_ndcg": per_seed}


def _fmt(m: tuple[float, float, float]) -> str:
    return f"{m[0]:.3f} [{m[1]:.3f}; {m[2]:.3f}]"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--protocol", choices=("a", "b", "strict", "all"), default="all")
    p.add_argument("--method", default="full", help="ranker from app.validation.matching.rank (full, bm25, keyword…)")
    p.add_argument("--clean", action="store_true",
                   help="comparable-data scenario: all tested, true grade shown, no false skills (labels unchanged)")
    args = p.parse_args()
    protos = ("strict", "a", "b") if args.protocol == "all" else (args.protocol,)
    print("| Протокол | Зёрна | Ранжирование | nDCG@10 [95 % ДИ] | P@10 | MRR | Потребностей (пропущено) |")
    print("|---|---|---|---|---|---|---|")
    for proto in protos:
        for name, seeds in (("2026–2028", PUBLIC_SEEDS), ("4001–4005", HOLDOUT_SEEDS)):
            s = summary(seeds, proto, args.method, args.clean)
            m = s["metrics"]
            label = f"{proto} (clean)" if args.clean else proto
            print(f"| {label} | {name} | {args.method} | {_fmt(m['ndcg'])} | {_fmt(m['p10'])} "
                  f"| {_fmt(m['mrr'])} | {s['needs']} ({s['skipped']}) |", flush=True)


if __name__ == "__main__":
    main()
