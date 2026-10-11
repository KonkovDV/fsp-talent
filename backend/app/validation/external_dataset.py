"""Our matching score on an external open synthetic benchmark: `python -m app.validation.external_dataset`.

Source: the public repository https://github.com/miliantr/fsp-talent, pinned to commit PINNED. Its files are not
copied into this repository: the command downloads them at run time (benchmark JSON and the reference catalogue
with the skill relations) and caches them under ~/.cache/fsp-external. The catalogue is read with `ast`, never
executed.

Labels 0..3 follow the rule published with the benchmark (utility = specialisation x grade x skill coverage x
position inside the grade x salary, thresholds 0.8 / 0.6 / 0.4). nDCG@10 uses gain 2^rel - 1 and the ideal over the
whole pool, P@10 and MRR count labels >= 2, needs without a label >= 2 are skipped, as in the source evaluation.

Field mapping (ours, documented in docs/VALIDATION_MATCHING.md):
  spec -> role and test_spec; verified_grade -> grade, grade_source "assessed";
  theta_hat -> test_p = 1 / (1 + exp(-3 (theta_hat - cut of verified_grade))), test_n 12;
  declared_skills -> skills, trust "test_confirmed" (the benchmark verifies every candidate);
  work_format -> work_formats ("any" -> empty); job must / nice -> required / wanted skills;
  FSP history, salary, city and industry are not passed to our score.
`--declared` passes the self-declared grade and self-reported skills instead, without the test.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import statistics
import urllib.request
from pathlib import Path

from app.services.matching import CandidateFacts, NeedSpec, score
from app.services.search.pipeline import order_pool
from app.validation.matching import bootstrap_ci

PINNED = "d45eb7553d2d524e2b732f8936ea53a86b51e8cb"
RAW = f"https://raw.githubusercontent.com/miliantr/fsp-talent/{PINNED}/"
FILES = {"benchmark": "evaluation/data/matching_benchmark.json", "catalog": "backend/app/domain/catalog.py"}
CACHE = Path.home() / ".cache" / "fsp-external" / PINNED
GRADE_ORDER = ("junior", "middle", "senior")
CUT = {"junior": -1.0, "middle": 0.0, "senior": 1.0}
BAND_LOW = {"junior": -1.0, "middle": 0.0, "senior": 1.0}


def fetch(name: str) -> str:
    path = CACHE / Path(FILES[name]).name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(RAW + FILES[name], timeout=60) as r:  # noqa: S310 - fixed https URL
            path.write_bytes(r.read())
    return path.read_text(encoding="utf-8")


def parse_catalog(source: str) -> tuple[dict, dict]:
    """SPEC_SIMILARITY and the skill relations {slug: {related: weight}}, read as literals."""
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("SPEC_SIMILARITY", "SKILLS"):
                found[node.targets[0].id] = ast.literal_eval(node.value)
    related = {row[0]: dict(row[5]) for row in found["SKILLS"]}
    return found["SPEC_SIMILARITY"], related


def spec_sim(table: dict, a: str, b: str) -> float:
    return 1.0 if a == b else table.get((a, b)) or table.get((b, a)) or 0.0


def skill_sim(related: dict, have: str, need: str) -> float:
    if have == need:
        return 1.0
    return max(related.get(have, {}).get(need, 0.0), related.get(need, {}).get(have, 0.0))


def label(job: dict, c: dict, spec_table: dict, related: dict) -> int:
    sim = spec_sim(spec_table, c["spec"], job["spec"])
    spec_fit = 1.0 if sim >= 1 else 0.4 if sim >= 0.3 else 0.0
    d = GRADE_ORDER.index(c["true_grade"]) - GRADE_ORDER.index(job["grade"])
    grade_fit = {0: 1.0, 1: 0.75, -1: 0.45}.get(d, 0.0)
    cov = 0.0
    for s in job["must"]:
        best = max((skill_sim(related, t, s) for t in c["true_skills"]), default=0.0)
        cov += 1.0 if best >= 1 else 0.5 if best >= 0.5 else 0.0
    cov /= len(job["must"])
    ability = 0.85 + 0.3 * min(1.0, c["theta"] - BAND_LOW[c["true_grade"]]) if d == 0 else 1.0
    salary = 0.6 if c["expected_salary"] > job["salary_to"] * 1.3 else 1.0
    u = spec_fit * grade_fit * (0.25 + 0.75 * cov) * ability * salary
    return 3 if u >= 0.8 else 2 if u >= 0.6 else 1 if u >= 0.4 else 0


def to_facts(c: dict, declared: bool = False) -> CandidateFacts:
    formats = () if c["work_format"] == "any" else (c["work_format"],)
    if declared:
        return CandidateFacts(role=c["spec"], grade=c["declared_grade"], grade_source="declared",
                              skills={s: "self_reported" for s in c["declared_skills"]}, test_p=None,
                              test_spec=c["spec"], fsp_lcb=None, industry=None, work_formats=formats)
    p = 1.0 / (1.0 + math.exp(-3.0 * (c["theta_hat"] - CUT[c["verified_grade"]])))
    return CandidateFacts(role=c["spec"], grade=c["verified_grade"], grade_source="assessed",
                          skills={s: "test_confirmed" for s in c["declared_skills"]}, test_p=p,
                          test_spec=c["spec"], fsp_lcb=None, industry=None, test_correct=round(p * 12),
                          test_n=12, work_formats=formats)


def to_need(job: dict) -> NeedSpec:
    return NeedSpec(role=job["spec"], grade=job["grade"], skills=tuple(job["must"]), nice=tuple(job["nice"]),
                    industry=None, city=None, work_format=None if job["work_format"] == "any" else job["work_format"])


def metrics(ranked: list, labels: dict, k: int = 10) -> tuple[float, float, float]:
    rel = {i for i, v in labels.items() if v >= 2}
    top = ranked[:k]
    dcg = sum((2 ** labels.get(i, 0) - 1) / math.log2(n + 2) for n, i in enumerate(top))
    ideal = sorted(labels.values(), reverse=True)[:k]
    idcg = sum((2 ** v - 1) / math.log2(n + 2) for n, v in enumerate(ideal))
    mrr = next((1.0 / (n + 1) for n, i in enumerate(ranked) if i in rel), 0.0)
    return (dcg / idcg if idcg else 0.0), sum(i in rel for i in top) / k, mrr


def evaluate(data: dict, spec_table: dict, related: dict, declared: bool = False) -> dict:
    cands = data["candidates"]
    rows = []
    for job in data["jobs"]:
        labels = {c["id"]: label(job, c, spec_table, related) for c in cands}
        if not any(v >= 2 for v in labels.values()):
            continue
        need = to_need(job)
        scores, cold = {}, set()
        for c in cands:
            facts = to_facts(c, declared)
            scores[c["id"]] = score(need, facts).score
            if facts.test_n is None:
                cold.add(c["id"])
        ranked = order_pool([c["id"] for c in cands], scores, {}, {c["id"]: 0.0 for c in cands}, cold)
        rows.append(metrics(ranked, labels))
    out = {"needs": len(rows)}
    for i, name in enumerate(("ndcg", "p10", "mrr")):
        values = [r[i] for r in rows]
        out[name] = (statistics.mean(values), *bootstrap_ci(values))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--declared", action="store_true", help="self-declared grade and skills, no test")
    args = parser.parse_args()
    spec_table, related = parse_catalog(fetch("catalog"))
    data = json.loads(fetch("benchmark"))
    r = evaluate(data, spec_table, related, args.declared)
    fmt = lambda m: f"{m[0]:.3f} [{m[1]:.3f}; {m[2]:.3f}]"  # noqa: E731
    print(f"source {RAW}{FILES['benchmark']}")
    print(f"needs {r['needs']}, candidates {len(data['candidates'])}, input {'declared' if args.declared else 'verified'}")
    print(f"nDCG@10 {fmt(r['ndcg'])}  P@10 {fmt(r['p10'])}  MRR {fmt(r['mrr'])}")


if __name__ == "__main__":
    main()
