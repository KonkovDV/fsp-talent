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

Rankers: random, the resume baseline (count of declared required skills, then role and declared grade), the
production factor score (app.services.matching.score) and its ablations. Besides nDCG@10, P@min(10, n) and MAP
the run reports the Spearman correlation between the order inside the category the employer sees (same role,
same shown grade) and the hidden ability θ, the share of overrated people (shown grade above the real one) in
the top 10, bootstrap 95 % intervals over needs, and the same table on three consecutive seeds. The weights
were set by hand and are not fitted to this benchmark. The dataset is deterministic per seed and its SHA-256 is
printed; `--import` evaluates a labelled file in the same JSON format, `--pairs` a JSONL of jury pairs.
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
from app.services.skills import ROLES, TAXONOMY

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
        test_n = test_correct = None
        if test_p is not None:
            test_n = 12
            test_correct = int(round(test_p * test_n))
        has_fsp = rng.random() < 0.55
        lcb = max(0.0, min(0.9, 0.3 + 0.15 * theta + rng.gauss(0, 0.08))) if has_fsp else None
        candidates.append({
            "id": f"c{i}",
            "truth": {"role": role, "grade": true_grade, "skills": true_skills, "theta": round(theta, 4)},
            "observed": {"role": role, "grade": grade, "grade_source": source, "skills": declared,
                         "test_p": test_p, "test_correct": test_correct, "test_n": test_n,
                         "fsp_lcb": lcb, "industry": rng.choice(INDUSTRIES)},
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


def cohen_kappa(left: list[int], right: list[int]) -> float:
    """Unweighted Cohen's kappa. 1 when the two raters always agree, 0 when they match by chance."""
    if len(left) != len(right) or not left:
        raise ValueError("kappa needs two equal non-empty lists")
    n = len(left)
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / n
    cats = set(left) | set(right)
    chance = sum((left.count(c) / n) * (right.count(c) / n) for c in cats)
    if chance >= 1.0:
        return 1.0
    return (observed - chance) / (1.0 - chance)


def blind_label(need: dict, observed: dict, rng: random.Random) -> int:
    """A rater who sees only the noisy profile and then slips by one step one time in five.

    The rubric is the relevance rule applied to the declared profile, not to the hidden truth
    and not to the production score. The slip comes from `rng`, which the caller builds with its own seed.
    """
    role = observed.get("role")
    role_ok = role == need.get("role")
    near = role_ok or role in ROLE_NEIGHBOURS.get(need.get("role"), set())
    skills = observed.get("skills") or {}
    required = list(need.get("skills") or [])
    have = sum(1 for skill in required if skill in skills)
    try:
        gap = abs(GRADES.index(observed.get("grade")) - GRADES.index(need.get("grade")))
    except ValueError:
        gap = 9
    if role_ok and required and have == len(required) and gap == 0:
        label = 3
    elif near and required and have == len(required) and gap <= 1:
        label = 2
    elif near and required and have * 2 >= len(required):
        label = 1
    else:
        label = 0
    if rng.random() < 0.20:
        label = min(3, label + 1) if rng.random() < 0.5 else max(0, label - 1)
    return label


def blind_kappa(dataset: dict, seed: int) -> float:
    """Cohen's kappa of the blind rater against labels that were computed from the hidden truth."""
    rng = random.Random(seed)
    oracle: list[int] = []
    blind: list[int] = []
    by_id = {c["id"]: c for c in dataset["candidates"]}
    for need in dataset["needs"]:
        for cid, label in dataset["labels"][need["id"]].items():
            oracle.append(int(label))
            blind.append(blind_label(need, by_id[cid]["observed"], rng))
    return cohen_kappa(oracle, blind)


def sha256(dataset: dict) -> str:
    return hashlib.sha256(json.dumps(dataset, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _facts(c: dict) -> CandidateFacts:
    o = c["observed"]
    return CandidateFacts(role=o["role"], grade=o["grade"], grade_source=o["grade_source"], skills=dict(o["skills"]),
                          test_p=o["test_p"], test_spec=o["role"], fsp_lcb=o["fsp_lcb"], industry=o["industry"],
                          test_correct=o.get("test_correct"), test_n=o.get("test_n"))


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
             "no_fsp": {"use_fsp": False}, "no_evidence": {"use_test": False, "use_fsp": False},
             "no_related": {"use_related": False}}[method]
    spec = _spec(need)
    scored = [(score(spec, _facts(c), **flags).score, c["id"]) for c in cands]
    return [cid for _, cid in sorted(scored, key=lambda t: (-t[0], t[1]))]


def ndcg(ranked: list[str], labels: dict[str, int], k: int = 10) -> float:
    dcg = sum((2 ** labels.get(cid, 0) - 1) / math.log2(i + 2) for i, cid in enumerate(ranked[:k]))
    ideal = sorted(labels.values(), reverse=True)[:k]
    idcg = sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def precision(ranked: list[str], labels: dict[str, int], k: int = 10) -> float:
    """P@min(k, n): with three labelled pairs the top three are judged, not ten seats."""
    seats = min(k, len(labels)) or 1
    return sum(1 for cid in ranked[:seats] if labels.get(cid, 0) >= 2) / seats


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


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2.0
        i = j + 1
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation with average ranks for ties. None when either side is constant."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if not sx or not sy:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True)) / (sx * sy)


CATEGORY_MIN = 5


def category_spearman(ranked: list[str], need: dict, by_id: dict[str, dict]) -> float | None:
    """Order inside the category the employer sees (role and shown grade equal the need) against hidden θ.

    The category is what the platform shows, so it holds people whose declared grade is too high. A ranker
    that lifts the stronger ones inside it has a positive correlation. Needs with fewer than five people
    in the category are skipped.
    """
    members = [cid for cid in ranked
               if by_id[cid]["observed"]["role"] == need["role"] and by_id[cid]["observed"]["grade"] == need["grade"]]
    if len(members) < CATEGORY_MIN:
        return None
    return spearman([-float(i) for i in range(len(members))], [by_id[c]["truth"]["theta"] for c in members])


def overrated_share(ranked: list[str], by_id: dict[str, dict], k: int = 10) -> float:
    """Share of the top k whose shown grade is above the real one."""
    top = ranked[:k]
    over = sum(1 for cid in top
               if GRADES.index(by_id[cid]["observed"]["grade"]) > GRADES.index(by_id[cid]["truth"]["grade"]))
    return over / max(1, len(top))


def bootstrap_ci(values: list[float], seed: int = 11, rounds: int = 1000) -> tuple[float, float]:
    """95 % percentile interval of the mean, resampling needs with replacement."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(statistics.mean(rng.choices(values, k=n)) for _ in range(rounds))
    return means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]


@dataclass
class Row:
    method: str
    ndcg10: float
    p10: float
    map: float
    rho: float | None = None              # Spearman inside the category against hidden θ
    overrated: float | None = None        # share of the top 10 whose shown grade is above the real one
    ndcg_ci: tuple[float, float] | None = None
    rho_ci: tuple[float, float] | None = None


METHODS = ("random", "keyword", "full", "no_trust", "no_test", "no_fsp", "no_evidence", "no_related")
TITLES = {"random": "Случайный порядок", "keyword": "Базовая линия «по резюме»: заявленные навыки и грейд",
          "full": "ФСП Талант: оценка соответствия", "no_trust": "  без весов доверия к навыкам",
          "no_test": "  без теста", "no_fsp": "  без оси ФСП", "no_evidence": "  без теста и без ФСП",
          "no_related": "  без близких технологий"}


def evaluate(dataset: dict, seed: int = 1) -> list[Row]:
    rng = random.Random(seed)
    rows = []
    needs = [n for n in dataset["needs"] if any(v >= 2 for v in dataset["labels"][n["id"]].values())]
    by_id = {c["id"]: c for c in dataset["candidates"]}
    hidden = bool(dataset["candidates"]) and "theta" in (dataset["candidates"][0].get("truth") or {})
    for method in METHODS:
        nd, pr, ap, rho, over = [], [], [], [], []
        for need in needs:
            ranked = rank(dataset, need, method, rng)
            labels = dataset["labels"][need["id"]]
            nd.append(ndcg(ranked, labels))
            pr.append(precision(ranked, labels))
            ap.append(average_precision(ranked, labels))
            if hidden:
                over.append(overrated_share(ranked, by_id))
                r = category_spearman(ranked, need, by_id)
                if r is not None:
                    rho.append(r)
        rows.append(Row(method, statistics.mean(nd), statistics.mean(pr), statistics.mean(ap),
                        statistics.mean(rho) if rho else None, statistics.mean(over) if over else None,
                        bootstrap_ci(nd), bootstrap_ci(rho) if rho else None))
    return rows


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _ci(ci: tuple[float, float] | None) -> str:
    return "—" if ci is None else f"{ci[0]:.3f}…{ci[1]:.3f}"


def markdown(rows: list[Row], dataset: dict) -> str:
    n_needs = sum(1 for n in dataset["needs"] if any(v >= 2 for v in dataset["labels"][n["id"]].values()))
    lines = [f"Набор: {len(dataset['candidates'])} кандидатов, {n_needs} потребностей с релевантными кандидатами, "
             f"seed {dataset.get('seed')}, SHA-256 `{sha256(dataset)[:16]}…`.", "",
             "| Ранжирование | nDCG@10 | 95 % ДИ nDCG | P@10, оценка ≥ 2 | MAP | Спирмен внутри категории "
             "| 95 % ДИ Спирмена | Завышенный грейд в топ-10 |",
             "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {TITLES[r.method]} | {r.ndcg10:.3f} | {_ci(r.ndcg_ci)} | {r.p10:.3f} | {r.map:.3f} "
              f"| {_num(r.rho)} | {_ci(r.rho_ci)} | {_pct(r.overrated)} |" for r in rows]
    return "\n".join(lines) + "\n"


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f} %"


def seeds_table(seeds: list[int], n_candidates: int, n_needs: int) -> tuple[str, dict[str, dict[str, float]]]:
    """The same benchmark on several seeds: mean and spread, so one lucky seed cannot carry a claim."""
    keys = ("keyword", "full", "no_test", "no_fsp", "no_evidence")
    per: dict[str, dict[str, list[float]]] = {k: {"ndcg": [], "rho": [], "over": []} for k in keys}
    for sd in seeds:
        rows = {r.method: r for r in evaluate(make_dataset(n_candidates, n_needs, sd))}
        for k in keys:
            per[k]["ndcg"].append(rows[k].ndcg10)
            per[k]["rho"].append(rows[k].rho if rows[k].rho is not None else float("nan"))
            per[k]["over"].append(rows[k].overrated or 0.0)

    def ms(xs: list[float], scale: float = 1.0, digits: int = 3) -> str:
        sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
        return f"{statistics.mean(xs) * scale:.{digits}f} ± {sd * scale:.{digits}f}"

    lines = [f"Зёрна {', '.join(map(str, seeds))}: среднее ± стандартное отклонение.", "",
             "| Ранжирование | nDCG@10 | Спирмен внутри категории | Завышенный грейд в топ-10, % |",
             "|---|---|---|---|"]
    lines += [f"| {TITLES[k].strip()} | {ms(per[k]['ndcg'])} | {ms(per[k]['rho'])} | {ms(per[k]['over'], 100, 1)} |"
              for k in keys]
    summary = {k: {m: statistics.mean(v) for m, v in per[k].items()} for k in keys}
    return "\n".join(lines) + "\n", summary


def load_pairs(path: str) -> dict:
    """JSONL of jury pairs: each line is need, candidate.observed and label 0..3.

    A JSON object in the same shape as --export is accepted too.
    """
    text = open(path, encoding="utf-8").read().strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    # One JSON object (possibly pretty-printed) versus one pair per line.
    if not (len(lines) > 1 and all(ln.lstrip().startswith("{") for ln in lines)):
        return json.loads(text)
    needs: dict[str, dict] = {}
    candidates: dict[str, dict] = {}
    labels: dict[str, dict[str, int]] = {}
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        need = dict(row["need"])
        obs = row["candidate"]
        observed = obs["observed"] if isinstance(obs, dict) and "observed" in obs else obs
        nid = str(need.get("id") or f"n{i}")
        cid = str(row.get("candidate_id") or (obs.get("id") if isinstance(obs, dict) else None) or f"c{i}")
        need["id"] = nid
        needs[nid] = need
        candidates[cid] = {"id": cid, "observed": observed}
        labels.setdefault(nid, {})[cid] = int(row["label"])
    return {"seed": None, "candidates": list(candidates.values()), "needs": list(needs.values()), "labels": labels}


# Thresholds of --check. They guard the claims in docs/VALIDATION_MATCHING.md, not a tuned optimum.
RHO_DROP = 0.05          # removing the test or the FSP axis must cost at least this much Spearman in the category
NDCG_FLOOR = 0.65        # full model on the default seed; the release before the category order had 0.661


def checks_ok(rows: list[Row], synthetic: bool = True) -> list[str]:
    """The production ranker beats the baselines; inside a category the test and the FSP axis both matter."""
    by = {r.method: r for r in rows}
    failed = []
    if not by["full"].ndcg10 > by["keyword"].ndcg10:
        failed.append("full nDCG@10 > keyword")
    if not by["full"].ndcg10 > by["random"].ndcg10:
        failed.append("full nDCG@10 > random")
    if not synthetic:
        return failed
    if by["full"].ndcg10 < NDCG_FLOOR:
        failed.append(f"full nDCG@10 >= {NDCG_FLOOR}")
    full_rho = by["full"].rho or 0.0
    for ablation in ("no_test", "no_fsp"):
        if full_rho - (by[ablation].rho or 0.0) < RHO_DROP:
            failed.append(f"Spearman full - {ablation} >= {RHO_DROP}")
    if not (by["full"].overrated or 0.0) < (by["keyword"].overrated or 0.0):
        failed.append("overrated in top 10: full < keyword")
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidates", type=int, default=800)
    parser.add_argument("--needs", type=int, default=80)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--seeds", type=int, default=3, help="repeat on this many consecutive seeds (0: skip)")
    parser.add_argument("--export", help="write the generated dataset (with labels) to this JSON file")
    parser.add_argument("--import", dest="imported", help="evaluate a labelled dataset in the same JSON format")
    parser.add_argument("--pairs", help="JSONL of jury pairs: need, candidate, label 0..3")
    parser.add_argument("--check", action="store_true", help="fail unless the thresholds in checks_ok hold")
    args = parser.parse_args()
    if args.pairs and args.imported:
        raise SystemExit("Укажите либо --pairs, либо --import")
    if args.pairs:
        dataset = load_pairs(args.pairs)
    elif args.imported:
        with open(args.imported, encoding="utf-8") as fh:
            dataset = json.load(fh)
    else:
        dataset = make_dataset(args.candidates, args.needs, args.seed)
    if args.export:
        with open(args.export, "w", encoding="utf-8") as fh:
            json.dump(dataset, fh, ensure_ascii=False)
    rows = evaluate(dataset)
    print(markdown(rows, dataset))
    synthetic = bool(dataset["candidates"]) and "theta" in (dataset["candidates"][0].get("truth") or {})
    by = {r.method: r for r in rows}
    if synthetic:
        print(f"внутри категории: Спирмен с полной моделью {_num(by['full'].rho)}, "
              f"без теста {_num(by['no_test'].rho)}, без ФСП {_num(by['no_fsp'].rho)}, "
              f"по резюме {_num(by['keyword'].rho)}")
        rater_seed = (args.seed or 0) + 1
        print(f"слепая разметка против оракула: каппа Коэна {blind_kappa(dataset, rater_seed):.2f} "
              f"(зерно разметчика {rater_seed}, набор размечен по скрытой правде и это зерно не видит)")
        if args.seeds and not args.imported:
            table, _ = seeds_table([args.seed + i for i in range(args.seeds)], args.candidates, args.needs)
            print()
            print(table)
    print("sha256", sha256(dataset))
    if args.check:
        failed = checks_ok(rows, synthetic)
        print("checks:", "failed " + ", ".join(failed) if failed else "passed")
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()


__all__ = ["make_dataset", "evaluate", "relevance", "sha256", "Row", "asdict"]
