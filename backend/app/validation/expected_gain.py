"""Expected-gain ranking: a pre-registered experiment (docs/PREREG_MATCHING_2026-10.md).

    python -m app.validation.expected_gain            # development seeds 2027, 2028
    python -m app.validation.expected_gain --holdout  # hold-out seeds 5001–5010, run once after the prereg commit

Idea. nDCG rewards the expected gain 2^rel − 1 at each position, so the order that maximises expected DCG sorts
by E[2^rel − 1 | what the platform observes] (probability ranking principle, Robertson 1977; for graded gains see
Järvelin & Kekäläinen 2002). The relevance rule is known (role, every required skill real, grade gap), so
E[gain] needs two calibrated beliefs:
  - P(skill is real | its trust level): test-confirmed, resume-confirmed, self-reported, missing;
  - P(real grade = shown + d | grade source): the test sharpens this, a declared grade is often one step high.
Both are counted on a calibration seed (2026) only. The ablation "no test, no FSP" is calibrated the same way
on what it sees: the grade source is hidden from it, so the declared and the test-confirmed grade share one
belief. Test and FSP then add a small, monotone lift (LAMBDA × the stronger of the two), never a penalty:
FSP does not enter the grade belief, so a better FSP result never lowers the value (TZ Q&A: FSP moves a
candidate only up, only inside the category).

This module is a measurement. It does not change the product order.
"""
from __future__ import annotations

import argparse
import collections
import random
import statistics

from app.services.matching import GRADES, ROLE_NEIGHBOURS
from app.validation import matching as V

CALIBRATION_SEEDS = (2026,)
DEV_SEEDS = (2027, 2028)
HOLDOUT_SEEDS = tuple(range(5001, 5011))
LAMBDA_GRID = (0.1, 0.3, 0.6, 1.0)
# Chosen on DEV_SEEDS before the hold-out was generated: the largest λ whose paired test against the ablation
# had p < 0.05 there (0.3: Δ nDCG +0.0096, p 0.014; 0.6: +0.0054, p 0.21). See the prereg.
LAMBDA = 0.3
UNTESTED_EVIDENCE = 0.2
FSP_FULL_LCB = 0.6
TRUST_LEVELS = ("test_confirmed", "resume_confirmed", "self_reported", "missing")


def calibrate(seeds=CALIBRATION_SEEDS, use_test: bool = True, n_candidates: int = 800, n_needs: int = 80):
    """Laplace-smoothed frequencies on the calibration seeds. Returns (skill belief, grade belief)."""
    real = collections.Counter()
    seen = collections.Counter()
    gaps = collections.Counter()
    per_source = collections.Counter()
    for seed in seeds:
        data = V.make_dataset(n_candidates, n_needs, seed)
        for c in data["candidates"]:
            obs, truth = c["observed"], c["truth"]
            source = obs["grade_source"] if use_test else "any"
            gaps[(source, GRADES.index(truth["grade"]) - GRADES.index(obs["grade"]))] += 1
            per_source[source] += 1
            for need in data["needs"]:
                for skill in need["skills"]:
                    level = obs["skills"].get(skill, "missing")
                    seen[level] += 1
                    real[level] += skill in truth["skills"]
    skills = {level: (real[level] + 1) / (seen[level] + 2) for level in TRUST_LEVELS}
    grades: dict[str, dict[int, float]] = {}
    for (source, gap), count in gaps.items():
        grades.setdefault(source, {})[gap] = count / per_source[source]
    return skills, grades


def _relevance(role_ok: bool, near: bool, have: int, m: int, gap: int) -> int:
    # Same rule as matching.relevance, on a count of real required skills and a grade gap.
    if role_ok and have == m and gap == 0:
        return 3
    if near and have == m and gap <= 1:
        return 2
    if near and have * 2 >= m:
        return 1
    return 0


def expected_gain(need: dict, obs: dict, skills: dict, grades: dict, use_test: bool = True) -> float:
    role_ok = obs["role"] == need["role"]
    near = role_ok or obs["role"] in ROLE_NEIGHBOURS.get(need["role"], set())
    probs = [skills[obs["skills"].get(s, "missing")] for s in need["skills"]]
    count = [1.0]   # Poisson-binomial over the required skills
    for p in probs:
        count = [(count[k] if k < len(count) else 0.0) * (1 - p) + (count[k - 1] * p if k else 0.0)
                 for k in range(len(count) + 1)]
    source = obs["grade_source"] if use_test else "any"
    shown, wanted = GRADES.index(obs["grade"]), GRADES.index(need["grade"])
    value = 0.0
    for gap, p_gap in grades[source].items():
        real = shown + gap
        if not 0 <= real < len(GRADES):
            continue
        for have, p_have in enumerate(count):
            value += p_gap * p_have * (2 ** _relevance(role_ok, near, have, len(probs), abs(real - wanted)) - 1)
    return value


def evidence(obs: dict, use_test: bool, use_fsp: bool) -> float:
    """The stronger of the test probability and the FSP factor; an absent source is neutral, not a minus."""
    parts = []
    if use_test and obs.get("test_p") is not None:
        parts.append(float(obs["test_p"]))
    if use_fsp and obs.get("fsp_lcb") is not None:
        parts.append(min(1.0, float(obs["fsp_lcb"]) / FSP_FULL_LCB))
    return max(parts) if parts else UNTESTED_EVIDENCE


def value(need: dict, obs: dict, beliefs, use_test: bool = True, use_fsp: bool = True, lam: float = LAMBDA) -> float:
    skills, grades = beliefs
    base = expected_gain(need, obs, skills, grades, use_test)
    lift = max(0.0, evidence(obs, use_test, use_fsp) - UNTESTED_EVIDENCE) if (use_test or use_fsp) else 0.0
    return base + lam * lift


def per_need(seeds, lam: float = LAMBDA, overclaim: float | None = None, n_candidates: int = 800, n_needs: int = 80):
    """Per-need nDCG@10, within-category Spearman and overclaim for EG full, EG ablation and the product."""
    full_beliefs = calibrate(use_test=True)
    ablation_beliefs = calibrate(use_test=False)
    out = {k: collections.defaultdict(list) for k in ("ndcg", "rho", "over")}
    for seed in seeds:
        data = V.make_dataset(n_candidates, n_needs, seed, overclaim=overclaim)
        by_id = {c["id"]: c for c in data["candidates"]}
        for need in data["needs"]:
            labels = data["labels"][need["id"]]
            if V._relevant(labels) == 0:
                continue
            ranked = {}
            for name, beliefs, use_test, use_fsp in (("eg_full", full_beliefs, True, True),
                                                     ("eg_no_evidence", ablation_beliefs, False, False)):
                scores = {c["id"]: value(need, c["observed"], beliefs, use_test, use_fsp, lam)
                          for c in data["candidates"]}
                ranked[name] = sorted(scores, key=lambda cid: (-scores[cid], cid))
            for method in ("full", "no_evidence"):
                ranked["product_" + method] = V.rank(data, need, method, random.Random(0))
            for name, order in ranked.items():
                out["ndcg"][name].append(V.ndcg(order, labels))
                out["over"][name].append(V.overrated_share(order, by_id))
                rho = V.category_spearman(order, need, by_id)
                out["rho"][name].append(rho)
    return out


def _paired(a: list, b: list) -> tuple[float, float, float, float]:
    pairs = [(x, y) for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    return V.sign_permutation([x - y for x, y in pairs])


def report(seeds, lam: float = LAMBDA, overclaim: float | None = None) -> str:
    res = per_need(seeds, lam, overclaim)
    names = ("eg_full", "eg_no_evidence", "product_full", "product_no_evidence")
    lines = [f"seeds {seeds[0]}…{seeds[-1]} ({len(seeds)}), λ={lam}, overclaim={overclaim}",
             "| Ранжирование | nDCG@10 | Спирмен в категории | Завышенный грейд в топ-10 |", "|---|---|---|---|"]
    for name in names:
        rhos = [r for r in res["rho"][name] if r is not None]
        lines.append(f"| {name} | {statistics.mean(res['ndcg'][name]):.4f} | {statistics.mean(rhos):.3f} | "
                     f"{100 * statistics.mean(res['over'][name]):.1f} % |")
    lines += ["", "| Сравнение | Метрика | Δ | 95 % ДИ | p |", "|---|---|---|---|---|"]
    for left, right in (("eg_full", "eg_no_evidence"), ("eg_full", "product_full"),
                        ("eg_full", "product_no_evidence")):
        for metric in ("ndcg", "rho"):
            mean, low, high, p = _paired(res[metric][left], res[metric][right])
            lines.append(f"| {left} − {right} | {metric} | {mean:+.4f} | {low:+.4f}…{high:+.4f} | {p:.4f} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--lambda-grid", action="store_true", help="the dev sweep that chose LAMBDA")
    parser.add_argument("--overclaim", type=float, default=None, help="misspecified generator, beliefs frozen")
    args = parser.parse_args()
    seeds = HOLDOUT_SEEDS if args.holdout else DEV_SEEDS
    if args.lambda_grid:
        for lam in LAMBDA_GRID:
            print(report(DEV_SEEDS, lam))
            print()
        return
    print(report(seeds, LAMBDA, args.overclaim))


if __name__ == "__main__":
    main()
