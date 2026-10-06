"""Offline evaluation of candidate ranking: `python -m app.validation.matching [--needs 80] [--export f.json]`.

Labelled employer–candidate pairs do not exist for the hackathon, so the benchmark is synthetic and says so.
Each candidate has a hidden truth (real skills, real level) and noisy observations the platform sees:
declared skills miss 25 % of the real ones and add 15 % false ones; the declared grade is one level too high
for 30 % of people; a test (taken by 45 %) confirms real skills and measures the level; 55 % have FSP history
whose LCB correlates with the level. Relevance labels come from the hidden truth only:

    3  role matches, all required skills are real, real grade equals the requested one
    2  role matches or is adjacent, all required skills are real, grade within one level
    1  role matches or is adjacent, at least half of the required skills are real
    0  otherwise

Rankers: random, a keyword baseline (count of declared required skills, then declared grade), the production
factor score (app.services.matching.score) and its ablations. The weights were set by hand before this
benchmark existed and are not fitted to it. The dataset is deterministic per seed and its SHA-256 is printed,
so anyone can regenerate and check it; `--import` evaluates a jury-labelled file in the same JSON format.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass

from app.services.matching import GRADES, ROLE_NEIGHBOURS, CandidateFacts, NeedSpec, score
from app.services.skills import TAXONOMY

ROLES = ("backend", "frontend", "fullstack", "ml", "devops", "security", "embedded", "mobile")
CUTS = {"intern": -2.5, "junior": -1.5, "middle": -0.5, "senior": 0.5, "lead": 1.5}
TESTABLE = {"Python", "SQL", "JavaScript", "Algorithms", "Networking", "Web Security", "Machine Learning", "C"}
INDUSTRIES = ("fintech", "ecommerce", "gamedev", "edtech", "govtech", "telecom", "industry", "any")


def _pool(role: str) -> list[str]:
    return sorted(name for name, (roles, _) in TAXONOMY.items() if role in roles)


def _grade(theta: float) -> str:
    g = "intern"
    for name, cut in CUTS.items():
        if theta >= cut:
            g = name
    return g


def make_dataset(n_candidates: int = 800, n_needs: int = 80, seed: int = 2026) -> dict:
    rng = random.Random(seed)
    candidates = []
    for i in range(n_candidates):
        role = rng.choice(ROLES)
        theta = rng.gauss(0.0, 1.0)
        pool = _pool(role)
        true_skills = sorted(rng.sample(pool, k=min(len(pool), rng.randint(4, 8))))
        declared = {s: "self_reported" for s in true_skills if rng.random() > 0.25}
        others = [s for s in pool if s not in true_skills]
        p_false = 0.15 * len(true_skills) / max(1, len(others))   # ~15 % of declared skills are false
        for s in others:
            if rng.random() < p_false:
                declared.setdefault(s, "self_reported")
        for s in list(declared):
            if s in true_skills and rng.random() < 0.3:
                declared[s] = "resume_confirmed"
        true_grade = _grade(theta)
        gi = GRADES.index(true_grade)
        r = rng.random()
        declared_grade = (GRADES[min(gi + 1, len(GRADES) - 1)] if r < 0.30
                          else GRADES[max(gi - 1, 0)] if r < 0.40 else true_grade)
        tested = rng.random() < 0.45
        grade, source, test_p = declared_grade, "declared", None
        if tested:
            test_p = 1.0 / (1.0 + math.exp(-3.0 * (theta - CUTS[declared_grade])))
            if test_p >= 0.75:
                grade, source = declared_grade, "assessed"
            else:
                test_p = None
            for s in true_skills:
                if s in TESTABLE and rng.random() < 0.9:
                    declared[s] = "test_confirmed"
        has_fsp = rng.random() < 0.55
        lcb = max(0.0, min(0.9, 0.3 + 0.15 * theta + rng.gauss(0, 0.08))) if has_fsp else None
        candidates.append({
            "id": f"c{i}", "truth": {"role": role, "grade": true_grade, "skills": true_skills},
            "observed": {"role": role, "grade": grade, "grade_source": source, "skills": declared,
                         "test_p": test_p, "fsp_lcb": lcb, "industry": rng.choice(INDUSTRIES)},
        })
    needs = []
    for j in range(n_needs):
        role = rng.choice(ROLES)
        pool = _pool(role)
        req = sorted(rng.sample(pool, k=min(len(pool), rng.randint(2, 3))))
        nice = sorted(rng.sample([s for s in pool if s not in req], k=min(1, max(0, len(pool) - len(req)))))
        needs.append({"id": f"n{j}", "role": role, "grade": rng.choice(GRADES), "skills": req, "nice": nice,
                      "industry": None})
    labels = {n["id"]: {c["id"]: relevance(n, c["truth"]) for c in candidates} for n in needs}
    return {"seed": seed, "candidates": candidates, "needs": needs, "labels": labels}


def relevance(need: dict, truth: dict) -> int:
    role_ok = truth["role"] == need["role"]
    near = role_ok or truth["role"] in ROLE_NEIGHBOURS.get(need["role"], set())
    have = sum(1 for s in need["skills"] if s in truth["skills"])
    gap = abs(GRADES.index(truth["grade"]) - GRADES.index(need["grade"]))
    if role_ok and have == len(need["skills"]) and gap == 0:
        return 3
    if near and have == len(need["skills"]) and gap <= 1:
        return 2
    if near and have * 2 >= len(need["skills"]):
        return 1
    return 0


def sha256(dataset: dict) -> str:
    return hashlib.sha256(json.dumps(dataset, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _facts(c: dict) -> CandidateFacts:
    o = c["observed"]
    return CandidateFacts(role=o["role"], grade=o["grade"], grade_source=o["grade_source"], skills=dict(o["skills"]),
                          test_p=o["test_p"], test_spec=o["role"], fsp_lcb=o["fsp_lcb"], industry=o["industry"])


def _spec(n: dict) -> NeedSpec:
    return NeedSpec(role=n["role"], grade=n["grade"], skills=tuple(n["skills"]), nice=tuple(n.get("nice", ())),
                    industry=n.get("industry"))


def rank(dataset: dict, need: dict, method: str, rng: random.Random) -> list[str]:
    cands = dataset["candidates"]
    if method == "random":
        ids = [c["id"] for c in cands]
        rng.shuffle(ids)
        return ids
    if method == "keyword":
        def key(c):
            o = c["observed"]
            hits = sum(1 for s in need["skills"] if s in o["skills"])
            return (-hits, -(o["role"] == need["role"]), -(o["grade"] == need["grade"]), c["id"])
        return [c["id"] for c in sorted(cands, key=key)]
    flags = {"full": {}, "no_trust": {"use_trust": False}, "no_test": {"use_test": False},
             "no_fsp": {"use_fsp": False}, "no_related": {"use_related": False}}[method]
    spec = _spec(need)
    scored = [(score(spec, _facts(c), **flags).score, c["id"]) for c in cands]
    return [cid for _, cid in sorted(scored, key=lambda t: (-t[0], t[1]))]


def ndcg(ranked: list[str], labels: dict[str, int], k: int = 10) -> float:
    dcg = sum((2 ** labels.get(cid, 0) - 1) / math.log2(i + 2) for i, cid in enumerate(ranked[:k]))
    ideal = sorted(labels.values(), reverse=True)[:k]
    idcg = sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def precision(ranked: list[str], labels: dict[str, int], k: int = 10) -> float:
    return sum(1 for cid in ranked[:k] if labels.get(cid, 0) >= 2) / k


def average_precision(ranked: list[str], labels: dict[str, int]) -> float:
    relevant = sum(1 for v in labels.values() if v >= 2)
    if not relevant:
        return 0.0
    hits, total = 0, 0.0
    for i, cid in enumerate(ranked, 1):
        if labels.get(cid, 0) >= 2:
            hits += 1
            total += hits / i
    return total / relevant


@dataclass
class Row:
    method: str
    ndcg10: float
    p10: float
    map: float


METHODS = ("random", "keyword", "full", "no_trust", "no_test", "no_fsp", "no_related")
TITLES = {"random": "Случайный порядок", "keyword": "Базовая линия: совпадение заявленных навыков",
          "full": "FSP Talent: разложимый скор", "no_trust": "  без весов доверия к навыкам",
          "no_test": "  без теста", "no_fsp": "  без оси ФСП", "no_related": "  без близких технологий"}


def evaluate(dataset: dict, seed: int = 1) -> list[Row]:
    rng = random.Random(seed)
    rows = []
    needs = [n for n in dataset["needs"] if any(v >= 2 for v in dataset["labels"][n["id"]].values())]
    for method in METHODS:
        nd, pr, ap = [], [], []
        for need in needs:
            ranked = rank(dataset, need, method, rng)
            labels = dataset["labels"][need["id"]]
            nd.append(ndcg(ranked, labels))
            pr.append(precision(ranked, labels))
            ap.append(average_precision(ranked, labels))
        rows.append(Row(method, statistics.mean(nd), statistics.mean(pr), statistics.mean(ap)))
    return rows


def markdown(rows: list[Row], dataset: dict) -> str:
    n_needs = sum(1 for n in dataset["needs"] if any(v >= 2 for v in dataset["labels"][n["id"]].values()))
    lines = [f"Набор: {len(dataset['candidates'])} кандидатов, {n_needs} потребностей с релевантными кандидатами, "
             f"seed {dataset.get('seed')}, SHA-256 `{sha256(dataset)[:16]}…`.", "",
             "| Ранжирование | nDCG@10 | P@10 (оценка ≥ 2) | MAP |", "|---|---|---|---|"]
    lines += [f"| {TITLES[r.method]} | {r.ndcg10:.3f} | {r.p10:.3f} | {r.map:.3f} |" for r in rows]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidates", type=int, default=800)
    parser.add_argument("--needs", type=int, default=80)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--export", help="write the generated dataset (with labels) to this JSON file")
    parser.add_argument("--import", dest="imported", help="evaluate a labelled dataset in the same JSON format")
    args = parser.parse_args()
    if args.imported:
        with open(args.imported, encoding="utf-8") as fh:
            dataset = json.load(fh)
    else:
        dataset = make_dataset(args.candidates, args.needs, args.seed)
    if args.export:
        with open(args.export, "w", encoding="utf-8") as fh:
            json.dump(dataset, fh, ensure_ascii=False)
    print(markdown(evaluate(dataset), dataset))
    print("sha256", sha256(dataset))


if __name__ == "__main__":
    main()


__all__ = ["make_dataset", "evaluate", "relevance", "sha256", "Row", "asdict"]
