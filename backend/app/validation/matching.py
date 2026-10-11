"""Offline evaluation of candidate ranking: `python -m app.validation.matching [--needs 80] [--export f.json]`.

Labelled employer–candidate pairs do not exist for the hackathon, so the benchmark is synthetic and says so.
Each candidate has a hidden truth (real skills, real level) and noisy observations the platform sees:
declared skills miss 25 % of the real ones and add 15 % false ones; the declared grade is one level too high
for 30 % of people; a test (taken by 45 %) confirms real skills and measures the level, and a failed attempt is
observed as `failed_grade` (the production search reads it the same way); 55 % have FSP history
whose LCB correlates with the level. Relevance labels come from the hidden truth only:

    3  role matches, all required skills are real, real grade equals the requested one
    2  role matches or is adjacent, all required skills are real, grade within one level
    1  role matches or is adjacent, at least half of the required skills are real
    0  otherwise

Rankers: random, keyword search (Okapi BM25 of the need text against the profile text), the resume baseline
(count of declared required skills, then role and declared grade), the production order
(app.services.search.pipeline.order_pool on the factor score) and its ablations.
«Без квоты для новичков» is the previous sort by score alone. Besides nDCG@10, P@min(10, n) and MAP
the run reports the Spearman correlation between the order inside the category the employer sees (same role,
same shown grade) and the hidden ability θ, two top-10 shares (shown grade above the real one, and real grade
below the need's grade), bootstrap 95 % intervals over needs, and the same table on three consecutive seeds.
`--tier-delta` prints a fit-tier sweep and does not change the product order: the sweep of 07.10.2026 was
rejected. The weights
were set by hand and are not fitted to this benchmark. The dataset is deterministic per seed and its SHA-256 is
printed; `--import` evaluates a labelled file in the same JSON format, `--pairs` a JSONL of jury pairs.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import random
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from app.services import matching as matching_service
from app.services.matching import GRADES, ROLE_NEIGHBOURS, CandidateFacts, NeedSpec, category_band, score
from app.services.search.pipeline import order_pool
from app.services.skills import ROLES, TAXONOMY

CUTS = {"intern": -2.5, "junior": -1.5, "middle": -0.5, "senior": 0.5, "lead": 1.5}
TESTABLE = {"Python", "SQL", "JavaScript", "Algorithms", "Networking", "Web Security", "Machine Learning", "C"}
INDUSTRIES = ("fintech", "ecommerce", "gamedev", "edtech", "govtech", "telecom", "industry", "any")
# Настройка: тест 101..105, подбор 3001..3005.
# Отложенные, один прогон после фиксации кода: тест 201..205, подбор 4001..4005.
# Публичные 7 и 2026..2028 только печатают итог, на них ничего не подбирается.
HOLDOUT_SEEDS = (4001, 4002, 4003, 4004, 4005)


def _pool(role: str) -> list[str]:
    return sorted(name for name, (roles, _) in TAXONOMY.items() if role in roles)


def _grade(theta: float) -> str:
    g = "intern"
    for name, cut in CUTS.items():
        if theta >= cut:
            g = name
    return g


# Measurement error of the simulated test. 0 keeps the published benchmark: the test probability is then a
# noiseless function of the hidden θ. A real session estimates θ with error (RMSE ≈ 0,47 in
# app.validation.assessment), so `--test-noise 0.47` shows how much of the within-category order survives.
# The noise has its own random stream: the default dataset and its SHA-256 do not change.
TEST_NOISE_SD = 0.0


def make_dataset(n_candidates: int = 800, n_needs: int = 80, seed: int = 2026,
                 overclaim: float | None = None, clean: bool = False) -> dict:
    """`clean=True` is the comparable-data scenario: every candidate tested, grade shown as the true one, no false
    skills declared. Truth, labels and needs are drawn exactly as in the default world."""
    rng = random.Random(seed)
    noise = random.Random(seed + 4242)
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
            if rng.random() < p_false and not clean:
                declared.setdefault(s, "self_reported")
        for s in list(declared):
            if s in true_skills and rng.random() < 0.3:
                declared[s] = "resume_confirmed"
        true_grade = _grade(theta)
        gi = GRADES.index(true_grade)
        r = rng.random()
        if overclaim is None:
            declared_grade = (GRADES[min(gi + 1, len(GRADES) - 1)] if r < 0.30
                              else GRADES[max(gi - 1, 0)] if r < 0.40 else true_grade)
        else:
            # The sweep names only the share who claim one step up. Everyone else states the true grade.
            declared_grade = GRADES[min(gi + 1, len(GRADES) - 1)] if r < overclaim else true_grade
        drawn_tested = rng.random() < 0.45
        tested = drawn_tested or clean
        if clean:
            declared_grade = true_grade
        grade, source, test_p, failed_grade = declared_grade, "declared", None, None
        if tested:
            measured = theta + (noise.gauss(0.0, TEST_NOISE_SD) if TEST_NOISE_SD > 0 else 0.0)
            test_p = 1.0 / (1.0 + math.exp(-3.0 * (measured - CUTS[declared_grade])))
            if clean:
                test_p = max(test_p, 0.75)
            if test_p >= 0.75:
                grade, source = declared_grade, "assessed"
            else:
                # The platform stores the failed attempt (outcome "not_passed"); the grade stays declared.
                test_p, failed_grade = None, declared_grade
            for s in true_skills:
                # Extra clean-scenario tests do not draw from rng, so truth and needs stay those of the default world.
                if s in TESTABLE and (rng.random() < 0.9 if drawn_tested else True):
                    declared[s] = "test_confirmed"
        test_n = test_correct = None
        if test_p is not None:
            test_n = 12
            test_correct = int(round(test_p * test_n))
        has_fsp = rng.random() < 0.55
        lcb = max(0.0, min(0.9, 0.3 + 0.15 * theta + rng.gauss(0, 0.08))) if has_fsp else None
        observed = {"role": role, "grade": grade, "grade_source": source, "skills": declared,
                    "test_p": test_p, "test_correct": test_correct, "test_n": test_n,
                    "fsp_lcb": lcb, "industry": rng.choice(INDUSTRIES)}
        if failed_grade is not None:
            observed["failed_grade"] = failed_grade
        candidates.append({
            "id": f"c{i}",
            "truth": {"role": role, "grade": true_grade, "skills": true_skills, "theta": round(theta, 4)},
            "observed": observed,
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
    _attach_conditions(candidates, needs, seed)
    return {"seed": seed, "candidates": candidates, "needs": needs, "labels": labels}


def _attach_conditions(candidates: list, needs: list, seed: int) -> None:
    """City and format drawn after the labels. The relevance rule does not see them."""
    extra = random.Random(seed + 17)
    cities = ("Москва", "Санкт-Петербург", "Новосибирск", "Казань", "Екатеринбург")
    formats = ("remote", "office", "hybrid")
    for c in candidates:
        observed = c["observed"]
        observed["city"] = extra.choice(cities) if extra.random() < 0.85 else None
        observed["work_formats"] = [extra.choice(formats)]
    for n in needs:
        if extra.random() < 0.75:
            n["city"] = extra.choice(cities)
            n["work_format"] = extra.choice(formats)
        else:
            n["city"] = None
            n["work_format"] = None


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
                          test_correct=o.get("test_correct"), test_n=o.get("test_n"),
                          city=o.get("city"), work_formats=tuple(o.get("work_formats") or ()),
                          failed_grade=o.get("failed_grade"))


def _spec(n: dict) -> NeedSpec:
    return NeedSpec(role=n["role"], grade=n["grade"], skills=tuple(n["skills"]), nice=tuple(n.get("nice", ())),
                    industry=n.get("industry"), city=n.get("city"), work_format=n.get("work_format"))


# score: the product order. category_first is a measurement only; main() sets it from --order.
ORDER_MODEL = "score"

# Keyword-search baseline: Okapi BM25 with the textbook constants. The need text holds what an employer writes
# about the job (specialisation, grade, required and wanted skills); the profile text holds what a candidate
# shows (specialisation, shown grade, every declared skill, whatever its proof). City and work format are
# conditions, not keywords, and stay out of both texts. IDF and the average length come from the pool ranked.
BM25_K1 = 1.2
BM25_B = 0.75
_TOKEN = re.compile(r"[0-9a-zа-яё#+]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _role_words(role: str | None) -> str:
    from app.services.survey import SPECIALIZATIONS

    return f"{role or ''} {SPECIALIZATIONS.get(role, '') if role else ''}"


def need_text(need: dict) -> str:
    """What a keyword search gets from the need: specialisation, grade, required and wanted skills."""
    return " ".join([_role_words(need.get("role")), str(need.get("grade") or ""),
                     *(need.get("skills") or ()), *(need.get("nice") or ())])


def profile_text(observed: dict) -> str:
    """What a keyword search sees in a profile: specialisation, shown grade and every declared skill."""
    return " ".join([_role_words(observed.get("role")), str(observed.get("grade") or ""),
                     *sorted(observed.get("skills") or {})])


def bm25_rank(cands: list[dict], need: dict, k1: float = BM25_K1, b: float = BM25_B) -> list[str]:
    """Okapi BM25 of the need text over the pool's profile texts; ties broken by candidate id."""
    docs = [(c["id"], _tokens(profile_text(c.get("observed") or {}))) for c in cands]
    if not docs:
        return []
    n = len(docs)
    avg = sum(len(t) for _, t in docs) / n or 1.0
    df: dict[str, int] = {}
    for _, toks in docs:
        for term in set(toks):
            df[term] = df.get(term, 0) + 1
    query = _tokens(need_text(need))
    idf = {t: math.log(1.0 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5)) for t in set(query)}
    scored = []
    for cid, toks in docs:
        tf: dict[str, int] = {}
        for term in toks:
            tf[term] = tf.get(term, 0) + 1
        norm = k1 * (1.0 - b + b * len(toks) / avg)
        value = sum(idf[t] * tf[t] * (k1 + 1.0) / (tf[t] + norm) for t in query if t in tf)
        scored.append((-value, cid))
    return [cid for _, cid in sorted(scored)]


def rank(dataset: dict, need: dict, method: str, rng: random.Random) -> list[str]:
    cands = dataset["candidates"]
    if method == "random":
        ids = [c["id"] for c in cands]
        rng.shuffle(ids)
        return ids
    if method == "bm25":
        return bm25_rank(cands, need)
    if method == "self":
        # Self-description only: declared specialization, then declared grade; no skills, no test, no FSP.
        def self_key(c):
            o = c["observed"]
            return (-(o["role"] == need["role"]), -(o["grade"] == need["grade"]), c["id"])
        return [c["id"] for c in sorted(cands, key=self_key)]
    if method == "keyword":
        def key(c):
            o = c["observed"]
            hits = sum(1 for s in need["skills"] if s in o["skills"])
            return (-hits, -(o["role"] == need["role"]), -(o["grade"] == need["grade"]), c["id"])
        return [c["id"] for c in sorted(cands, key=key)]
    flags = {"full": {}, "no_trust": {"use_trust": False}, "no_test": {"use_test": False},
             "no_fsp": {"use_fsp": False}, "no_evidence": {"use_test": False, "use_fsp": False},
             "no_related": {"use_related": False}, "no_quota": {}}[method]
    use_test = flags.get("use_test", True)
    spec = _spec(need)
    scores: dict[str, float] = {}
    best: dict[str, float] = {}
    cold: set[str] = set()
    ids: list[str] = []
    tiers: dict[str, int] = {}
    confirmed: dict[str, int] = {}
    fits: dict[str, float] = {}
    for c in cands:
        facts = _facts(c)
        cid = c["id"]
        ids.append(cid)
        result = score(spec, facts, **flags)
        scores[cid] = result.score
        best[cid] = facts.fsp_lcb or 0.0
        tiers[cid] = result.tier or 0
        # An ablation that drops the test must not keep sorting by "the test confirmed the grade".
        confirmed[cid] = result.confirmed if use_test else 0
        fits[cid] = result.fit or 0.0
        if facts.test_n is None:
            cold.add(cid)
    if method == "no_quota":
        return [cid for cid, _ in sorted(scores.items(), key=lambda t: (-t[1], t[0]))]
    bands = None
    if ORDER_MODEL == "category_first":
        bands = {c["id"]: category_band(c["observed"]["role"], c["observed"]["grade"], need["role"], need["grade"])
                 for c in cands}
    if not matching_service.USE_FIT_TIERS:
        return order_pool(ids, scores, {}, best, cold, bands=bands)
    return order_pool(ids, scores, {}, best, cold, tiers=tiers, confirmed=confirmed, fits=fits, bands=bands)


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
    """Our definition: share of the top k whose shown grade is above the real one."""
    top = ranked[:k]
    over = sum(1 for cid in top
               if GRADES.index(by_id[cid]["observed"]["grade"]) > GRADES.index(by_id[cid]["truth"]["grade"]))
    return over / max(1, len(top))


def overrated_parts(ranked: list[str], by_id: dict[str, dict], k: int = 10) -> tuple[float, float]:
    """The same share, split by whether the shown grade was only declared or confirmed by the test.

    The two parts add up to overrated_share. The rank order is not an input this function changes.
    """
    top = ranked[:k]
    declared = assessed = 0
    for cid in top:
        person = by_id[cid]
        shown = GRADES.index(person["observed"]["grade"])
        real = GRADES.index(person["truth"]["grade"])
        if shown <= real:
            continue
        if person["observed"].get("grade_source") == "assessed":
            assessed += 1
        else:
            declared += 1
    n = max(1, len(top))
    return declared / n, assessed / n


def below_need_share(ranked: list[str], need: dict, by_id: dict[str, dict], k: int = 10) -> float:
    """The other definition: share of the top k whose real grade is below the grade the need asks for."""
    if need.get("grade") not in GRADES:
        return 0.0
    need_i = GRADES.index(need["grade"])
    top = ranked[:k]
    return sum(1 for cid in top if GRADES.index(by_id[cid]["truth"]["grade"]) < need_i) / max(1, len(top))


PAIRED = (
    ("bm25", "поиск по ключевым словам"),
    ("keyword", "по резюме"),
    ("no_test", "без теста"),
    ("no_fsp", "без оси ФСП"),
    ("no_evidence", "без доказательств"),
)


def sign_permutation(deltas: list[float], seed: int = 11, rounds: int = 10000) -> tuple[float, float, float, float]:
    """Mean difference, its 95 % bootstrap interval, and the two-sided sign-flip p-value."""
    if not deltas:
        return (float("nan"), float("nan"), float("nan"), float("nan"))
    mean = statistics.mean(deltas)
    rng = random.Random(seed)
    n = len(deltas)
    boot = sorted(statistics.mean(rng.choices(deltas, k=n)) for _ in range(rounds))
    low = boot[int(0.025 * rounds)]
    high = boot[int(0.975 * rounds) - 1]
    observed = abs(mean)
    hits = sum(
        abs(statistics.mean(delta if rng.randrange(2) else -delta for delta in deltas)) >= observed
        for _ in range(rounds)
    )
    return mean, low, high, hits / rounds


def _relevant(labels: dict[str, int]) -> int:
    return sum(1 for value in labels.values() if value >= 2)


def _at_k(ranked: list[str], labels: dict[str, int], k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for cid in ranked[:k] if labels.get(cid, 0) >= 2) / k


_CURVES: dict[tuple[int, int, int], dict] = {}


def seed_curves(seed: int, n_candidates: int, n_needs: int) -> dict:
    """paired_curves of one public seed, computed once per run: the paired table and the guard share it."""
    key = (seed, n_candidates, n_needs)
    if key not in _CURVES:
        _CURVES[key] = paired_curves(make_dataset(n_candidates, n_needs, seed))
    return _CURVES[key]


def paired_curves(dataset: dict) -> dict:
    """Per-need nDCG and within-category Spearman for the full model and the four comparisons.

    Needs with no relevant candidate stay out of the means. Their count is reported on its own.
    """
    rng = random.Random(0)
    labelled = [n for n in dataset["needs"] if _relevant(dataset["labels"][n["id"]]) > 0]
    by_id = {c["id"]: c for c in dataset["candidates"]}
    methods = ("full", *(key for key, _ in PAIRED))
    ndcg_by = {method: [] for method in methods}
    rho_by = {method: [] for method in methods}
    capped: list[float] = []
    r_precision: list[float] = []
    for need in labelled:
        labels = dataset["labels"][need["id"]]
        relevant = _relevant(labels)
        for method in methods:
            ranked = rank(dataset, need, method, rng)
            ndcg_by[method].append(ndcg(ranked, labels))
            rho = category_spearman(ranked, need, by_id)
            if rho is not None:
                rho_by[method].append(rho)
            if method == "full":
                capped.append(_at_k(ranked, labels, min(10, relevant)))
                r_precision.append(_at_k(ranked, labels, relevant))
    zeros = len(dataset["needs"]) - len(labelled)
    return {
        "ndcg": ndcg_by, "rho": rho_by, "zeros": zeros, "needs": len(dataset["needs"]),
        "p_capped": statistics.mean(capped) if capped else float("nan"),
        "r_precision": statistics.mean(r_precision) if r_precision else float("nan"),
    }


def paired_report(seeds: list[int], n_candidates: int, n_needs: int) -> str:
    """Full model minus each comparison, on the public seeds. The relevance label is not changed."""
    lines = [
        "Парное сравнение: полная модель минус строка, по потребностям. "
        "95 % ДИ — бутстреп среднего, 10 000 повторов. p — доля перестановок знака с не меньшим модулем.",
        "",
        "| Зерно | Сравнение | Δ nDCG@10 | 95 % ДИ | p | Δ Спирмен |",
        "|---|---|---|---|---|---|",
    ]
    for seed in seeds:
        curves = seed_curves(seed, n_candidates, n_needs)
        for key, title in PAIRED:
            delta = [a - b for a, b in zip(curves["ndcg"]["full"], curves["ndcg"][key], strict=True)]
            mean, low, high, p_value = sign_permutation(delta, seed=seed)
            full_rho = curves["rho"]["full"]
            other_rho = curves["rho"][key]
            if full_rho and len(full_rho) == len(other_rho):
                rho_delta = statistics.mean(a - b for a, b in zip(full_rho, other_rho, strict=True))
                rho_cell = f"{rho_delta:+.4f}"
            else:
                rho_cell = "—"
            lines.append(
                f"| {seed} | {title} | {mean:+.4f} | {low:+.4f}…{high:+.4f} | {p_value:.4f} | {rho_cell} |"
            )
        lines.append(
            f"| {seed} | нуль релевантных | {curves['zeros']} из {curves['needs']} | "
            f"P@min(10, R) {curves['p_capped']:.3f} | R-precision {curves['r_precision']:.3f} | |"
        )
    lines.append("")
    return "\n".join(lines)


HEADLINE_BASES = (("bm25", "поиск по ключевым словам (BM25)"), ("keyword", "сортировка по резюме"))
HEADLINE_AGAINST = {"bm25": "поиска по ключевым словам", "keyword": "сортировки по резюме"}


def baseline_deltas(seeds: list[int], n_candidates: int, n_needs: int, rounds: int = 10000) -> dict:
    """Full model minus each base, nDCG@10 and P@10, paired by need and pooled over the seeds.

    The needs are the ones `evaluate` scores (at least one candidate labelled 2 or higher). The 95 % interval is the
    percentile bootstrap of the paired mean over the pooled needs, `rounds` resamples, resampling seed 11.
    """
    per = {key: {"ndcg": [], "p10": []} for key in ("full", *(k for k, _ in HEADLINE_BASES))}
    by_seed: dict[int, dict[str, dict[str, float]]] = {}
    for seed in seeds:
        dataset = make_dataset(n_candidates, n_needs, seed)
        rng = random.Random(0)
        needs = [n for n in dataset["needs"] if _relevant(dataset["labels"][n["id"]]) > 0]
        local = {key: {"ndcg": [], "p10": []} for key in per}
        for need in needs:
            labels = dataset["labels"][need["id"]]
            for key in per:
                ranked = rank(dataset, need, key, rng)
                local[key]["ndcg"].append(ndcg(ranked, labels))
                local[key]["p10"].append(precision(ranked, labels))
        for key in per:
            for metric in ("ndcg", "p10"):
                per[key][metric].extend(local[key][metric])
        by_seed[seed] = {key: {m: statistics.mean(v) for m, v in local[key].items()} for key in per}
    out: dict = {"seeds": list(seeds), "needs": len(per["full"]["ndcg"]), "by_seed": by_seed,
                 "level": {key: {m: statistics.mean(v) for m, v in per[key].items()} for key in per}}
    for key, _ in HEADLINE_BASES:
        out[key] = {}
        for metric in ("ndcg", "p10"):
            deltas = [a - b for a, b in zip(per["full"][metric], per[key][metric], strict=True)]
            mean, low, high = _paired_bounds(deltas, seed=11, rounds=rounds)
            out[key][metric] = {"mean": mean, "low": low, "high": high,
                                "wins": sum(1 for d in deltas if d > 0) / len(deltas),
                                "losses": sum(1 for d in deltas if d < 0) / len(deltas)}
    return out


LADDER = (("random", "случайный порядок"), ("self", "самоописание: заявленные специализация и грейд"),
          ("bm25", "поиск по ключевым словам (BM25)"), ("keyword", "сортировка по резюме"))


def ladder(seeds: list[int], n_candidates: int, n_needs: int) -> dict:
    """Base ladder for comparison with other teams: nDCG@10, P@5, P@10 per ranker and the share of needs where
    the full model's nDCG@10 is strictly above / below each base. Needs with at least one label ≥ 2, pooled."""
    keys = ("full", *(k for k, _ in LADDER))
    per = {k: {"ndcg": [], "p5": [], "p10": []} for k in keys}
    for seed in seeds:
        dataset = make_dataset(n_candidates, n_needs, seed)
        rng = random.Random(0)
        for need in dataset["needs"]:
            labels = dataset["labels"][need["id"]]
            if _relevant(labels) == 0:
                continue
            for k in keys:
                ranked = rank(dataset, need, k, rng)
                per[k]["ndcg"].append(ndcg(ranked, labels))
                per[k]["p5"].append(_at_k(ranked, labels, 5))
                per[k]["p10"].append(_at_k(ranked, labels, 10))
    out = {"seeds": list(seeds), "needs": len(per["full"]["ndcg"]),
           "level": {k: {m: statistics.mean(v) for m, v in per[k].items()} for k in keys}, "wins": {}}
    for k, _ in LADDER:
        d = [a - b for a, b in zip(per["full"]["ndcg"], per[k]["ndcg"], strict=True)]
        out["wins"][k] = (sum(x > 0 for x in d) / len(d), sum(x < 0 for x in d) / len(d))
    return out


def ladder_markdown(result: dict) -> str:
    def dec(x: float) -> str:
        return f"{x:.3f}".replace(".", ",")
    seeds = ", ".join(map(str, result["seeds"]))
    lines = [f"Лестница баз, зёрна {seeds}, {result['needs']} потребностей с релевантными кандидатами. "
             "P@5 и P@10 — доля кандидатов с меткой ≥ 2 среди первых 5 и 10.", "",
             "| Ранжирование | nDCG@10 | P@5 | P@10 | Модель лучше / хуже по nDCG@10, доля потребностей |",
             "|---|---|---|---|---|"]
    for k, title in LADDER:
        lv, (w, lo) = result["level"][k], result["wins"][k]
        lines.append(f"| {title} | {dec(lv['ndcg'])} | {dec(lv['p5'])} | {dec(lv['p10'])} "
                     f"| {w * 100:.0f} % / {lo * 100:.0f} % |")
    lv = result["level"]["full"]
    lines.append(f"| ФСП Талант (полная модель) | {dec(lv['ndcg'])} | {dec(lv['p5'])} | {dec(lv['p10'])} | — |")
    lines.append("")
    return "\n".join(lines)


def _signed(value: float) -> str:
    return f"{value:+.3f}".replace(".", ",").replace("-", "−")


def baseline_markdown(result: dict) -> str:
    seeds = ", ".join(map(str, result["seeds"]))
    lines = [
        f"Полная модель против двух баз на зёрнах {seeds}: разница по потребностям, сводно "
        f"{result['needs']} потребностей с релевантными кандидатами. 95 % ДИ — парный бутстреп среднего "
        "по потребностям, 10 000 повторов.",
        "",
        "| База | nDCG@10 базы | Δ nDCG@10 | 95 % ДИ | P@10 базы | Δ P@10 | 95 % ДИ | nDCG модели выше / ниже |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for key, title in HEADLINE_BASES:
        row, level = result[key], result["level"][key]
        nd, pr = row["ndcg"], row["p10"]
        lines.append(
            f"| {title} | {level['ndcg']:.3f} | {nd['mean']:+.3f} | {nd['low']:+.3f}…{nd['high']:+.3f} "
            f"| {level['p10']:.3f} | {pr['mean']:+.3f} | {pr['low']:+.3f}…{pr['high']:+.3f} "
            f"| {nd['wins'] * 100:.0f} % / {nd['losses'] * 100:.0f} % |")
    full = result["level"]["full"]
    lines += ["", f"Полная модель: nDCG@10 {full['ndcg']:.3f}, P@10 {full['p10']:.3f}.", ""]
    head = [f"против {HEADLINE_AGAINST[key]} {_signed(result[key]['ndcg']['mean'])} "
            f"({_signed(result[key]['ndcg']['low'])}…{_signed(result[key]['ndcg']['high'])})"
            for key, _ in HEADLINE_BASES]
    lines.append("Заголовок, Δ nDCG@10 (95 % ДИ): " + ", ".join(head) + ".")
    lines.append("")
    return "\n".join(lines)


def bootstrap_ci(values: list[float], seed: int = 11, rounds: int = 1000) -> tuple[float, float]:
    """95 % percentile interval of the mean, resampling needs with replacement."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(statistics.mean(rng.choices(values, k=n)) for _ in range(rounds))
    return means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]


def stuff_skills(dataset: dict, share: float = 0.2, seed: int = 41,
                 trust: str = "self_reported") -> tuple[dict, set[str]]:
    """A copy where `share` of candidates declare every skill of their role. Truth and labels stay the same."""
    rng = random.Random(seed)
    data = copy.deepcopy(dataset)
    stuffed: set[str] = set()
    for c in data["candidates"]:
        if rng.random() >= share:
            continue
        stuffed.add(c["id"])
        skills = c["observed"]["skills"]
        for s in _pool(c["observed"]["role"]):
            if trust == "self_reported":
                skills.setdefault(s, trust)
            else:
                skills[s] = trust
    return data, stuffed


def stuffing_study(dataset: dict, share: float = 0.2, k: int = 10, seed: int = 41) -> list[dict]:
    """Share of skill stuffers in the top k, against their share among same-role candidates of the need.

    Ratio 1 means stuffing buys nothing. The keyword baseline shows what an unprotected ranking does.
    Perturbation study in the spirit of arXiv:2501.04316.
    """
    rng = random.Random(0)
    rows = []
    # Baseline: the platform takes every claimed skill as confirmed. Shows what the trust weights buy.
    for method, trust in (("full", "self_reported"), ("keyword", "self_reported"), ("full", "test_confirmed")):
        data, stuffed = stuff_skills(dataset, share, seed, trust)
        top_share, pool_share, ndcgs, before = [], [], [], []
        for need in data["needs"]:
            same = [c["id"] for c in data["candidates"] if c["observed"]["role"] == need["role"]]
            if not same:
                continue
            ranked = rank(data, need, method, rng)
            top = ranked[:k]
            top_share.append(sum(1 for cid in top if cid in stuffed) / len(top))
            # Control: the same people in the same top k before they stuffed their profiles.
            clean_top = rank(dataset, need, method, rng)[:k]
            before.append(sum(1 for cid in clean_top if cid in stuffed) / len(clean_top))
            pool_share.append(sum(1 for cid in same if cid in stuffed) / len(same))
            ndcgs.append(ndcg(ranked, data["labels"][need["id"]]))
        top_mean, pool_mean = statistics.mean(top_share), statistics.mean(pool_share)
        rows.append({"method": method if trust == "self_reported" else f"{method}, всё подтверждено",
                     "top": top_mean, "pool": pool_mean, "before": statistics.mean(before),
                     "ratio": top_mean / pool_mean if pool_mean else float("nan"),
                     "top_ci": bootstrap_ci(top_share), "ndcg": statistics.mean(ndcgs)})
    return rows


UNCONFIRMED_POLICIES = (
    ("product", "как в продукте: общий порядок по баллу"),
    ("demote", "все без подтверждённого грейда после подтверждённых"),
    ("hide", "без подтверждённого грейда скрыты"),
)


def _unconfirmed(c: dict) -> bool:
    return c["observed"].get("grade_source") != "assessed"


MULTIPLIERS = (0.0, 0.25, 0.5, 0.75, 1.0)


def multiplier_rank(dataset: dict, need: dict, m: float) -> list[str]:
    """Order by the model score, an unconfirmed grade multiplied by m. 1 keeps the score, 0 pushes them down."""
    spec = _spec(need)
    rows = []
    for c in dataset["candidates"]:
        value = score(spec, _facts(c)).score
        rows.append((-(value * m if _unconfirmed(c) else value), c["id"]))
    return [cid for _, cid in sorted(rows)]


def apply_unconfirmed_policy(ranked: list[str], by_id: dict[str, dict], policy: str) -> list[str]:
    """Reorder one ranking. The relevance labels are not touched, so a hidden relevant candidate is a loss."""
    if policy == "product":
        return list(ranked)
    confirmed = [cid for cid in ranked if not _unconfirmed(by_id[cid])]
    if policy == "hide":
        return confirmed
    if policy == "demote":
        return confirmed + [cid for cid in ranked if _unconfirmed(by_id[cid])]
    raise ValueError(policy)


def returned_share(ranked: list[str], labels: dict[str, int], by_id: dict[str, dict], k: int = 20) -> float:
    """Share of the relevant (label ≥ 2) unconfirmed candidates that reach the top k."""
    pool = [cid for cid, v in labels.items() if v >= 2 and _unconfirmed(by_id[cid])]
    if not pool:
        return float("nan")
    top = set(ranked[:k])
    return sum(1 for cid in pool if cid in top) / len(pool)


def unconfirmed_study(dataset: dict, rounds: int = 1000, seed: int = 11) -> list[dict]:
    """Show, demote or hide candidates whose grade the test has not confirmed (Q&A FTT.4).

    Per need: nDCG@10, P@10 and the share of relevant unconfirmed people in the top 20. Δ is paired by need
    against the product order; 95 % interval — percentile bootstrap over needs (`bootstrap_ci`).
    """
    rng = random.Random(0)
    by_id = {c["id"]: c for c in dataset["candidates"]}
    labelled = [n for n in dataset["needs"] if _relevant(dataset["labels"][n["id"]]) > 0]
    per: dict[str, dict[str, list[float]]] = {
        key: {"ndcg": [], "p10": [], "returned": []} for key, _ in UNCONFIRMED_POLICIES}
    for need in labelled:
        labels = dataset["labels"][need["id"]]
        base = rank(dataset, need, "full", rng)
        for key, _ in UNCONFIRMED_POLICIES:
            ranked = apply_unconfirmed_policy(base, by_id, key)
            per[key]["ndcg"].append(ndcg(ranked, labels))
            per[key]["p10"].append(_at_k(ranked, labels, 10))
            share = returned_share(ranked, labels, by_id)
            if not math.isnan(share):
                per[key]["returned"].append(share)
    for m in MULTIPLIERS:
        key = f"x{m}"
        per[key] = {"ndcg": [], "p10": [], "returned": []}
    for need in labelled:
        labels = dataset["labels"][need["id"]]
        for m in MULTIPLIERS:
            ranked = multiplier_rank(dataset, need, m)
            per[f"x{m}"]["ndcg"].append(ndcg(ranked, labels))
            per[f"x{m}"]["p10"].append(_at_k(ranked, labels, 10))
            share = returned_share(ranked, labels, by_id)
            if not math.isnan(share):
                per[f"x{m}"]["returned"].append(share)
    titles = [*UNCONFIRMED_POLICIES,
              *((f"x{m}", f"балл, неподтверждённым × {m:g}".replace(".", ",")) for m in MULTIPLIERS)]
    rows = []
    for key, title in titles:
        d_ndcg = [a - b for a, b in zip(per[key]["ndcg"], per["product"]["ndcg"], strict=True)]
        d_p10 = [a - b for a, b in zip(per[key]["p10"], per["product"]["p10"], strict=True)]
        rows.append({
            "policy": key, "title": title, "needs": len(labelled),
            "ndcg": statistics.mean(per[key]["ndcg"]), "p10": statistics.mean(per[key]["p10"]),
            "returned": statistics.mean(per[key]["returned"]) if per[key]["returned"] else float("nan"),
            "d_ndcg": statistics.mean(d_ndcg), "d_ndcg_ci": bootstrap_ci(d_ndcg, seed=seed, rounds=rounds),
            "d_p10": statistics.mean(d_p10), "d_p10_ci": bootstrap_ci(d_p10, seed=seed, rounds=rounds),
        })
    return rows


def unconfirmed_markdown(rows: list[dict], seed: int, n_candidates: int, n_needs: int) -> str:
    lines = [
        f"Неподтверждённый грейд: показывать, опускать или скрывать. Зерно {seed}, {n_candidates} кандидатов, "
        f"{n_needs} потребностей, учтено {rows[0]['needs'] if rows else 0} с релевантными. Δ — к порядку продукта, "
        "парно по потребностям, 95 % ДИ — бутстреп 1000 повторов. «Возвращены» — доля релевантных без "
        "подтверждённого грейда, попавших в топ-20.",
        "",
        "| Политика | nDCG@10 | Δ nDCG@10 (95 % ДИ) | P@10 | Δ P@10 (95 % ДИ) | Возвращены в топ-20 |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['title']} | {r['ndcg']:.4f} | "
            f"{r['d_ndcg']:+.4f} ({r['d_ndcg_ci'][0]:+.4f}…{r['d_ndcg_ci'][1]:+.4f}) "
            f"| {r['p10']:.4f} | {r['d_p10']:+.4f} ({r['d_p10_ci'][0]:+.4f}…{r['d_p10_ci'][1]:+.4f}) "
            f"| {'—' if math.isnan(r['returned']) else _pct(r['returned'])} |")
    lines.append("")
    return "\n".join(lines)


@dataclass
class Row:
    method: str
    ndcg10: float
    p10: float
    map: float
    rho: float | None = None              # Spearman inside the category against hidden θ
    overrated: float | None = None        # share of the top 10 whose shown grade is above the real one
    below_need: float | None = None       # share of the top 10 whose real grade is below the need's grade
    ndcg_ci: tuple[float, float] | None = None
    rho_ci: tuple[float, float] | None = None
    over_declared: float | None = None    # part of overrated whose grade was only declared
    over_assessed: float | None = None    # part of overrated whose test confirmed that grade
    p5: float | None = None               # P@min(5, n): the /evaluate «Разметить самому» summary


METHODS = ("random", "bm25", "keyword", "full", "no_quota", "no_trust", "no_test", "no_fsp", "no_evidence",
           "no_related")
TITLES = {"random": "Случайный порядок",
          "bm25": "Поиск по ключевым словам (BM25): текст потребности против текста профиля",
          "keyword": "Базовая линия «по резюме»: заявленные навыки и грейд",
          "full": "ФСП Талант: оценка соответствия", "no_quota": "  без квоты для новичков",
          "no_trust": "  без весов доверия к навыкам",
          "no_test": "  без теста", "no_fsp": "  без оси ФСП", "no_evidence": "  без теста и без ФСП",
          "no_related": "  без близких технологий"}


def evaluate(dataset: dict, seed: int = 1) -> list[Row]:
    rng = random.Random(seed)
    rows = []
    needs = [n for n in dataset["needs"] if any(v >= 2 for v in dataset["labels"][n["id"]].values())]
    by_id = {c["id"]: c for c in dataset["candidates"]}
    hidden = bool(dataset["candidates"]) and "theta" in (dataset["candidates"][0].get("truth") or {})
    for method in METHODS:
        nd, pr, pr5, ap, rho, over, below = [], [], [], [], [], [], []
        declared_part, assessed_part = [], []
        for need in needs:
            labels = dataset["labels"][need["id"]]
            # A jury sheet labels a handful of people. Rank those, not the rest of the bank.
            pool = dataset
            if len(labels) < len(dataset["candidates"]):
                chosen = set(labels)
                pool = {"candidates": [c for c in dataset["candidates"] if c["id"] in chosen]}
            ranked = rank(pool, need, method, rng)
            nd.append(ndcg(ranked, labels))
            pr.append(precision(ranked, labels))
            pr5.append(precision(ranked, labels, 5))
            ap.append(average_precision(ranked, labels))
            if hidden:
                over.append(overrated_share(ranked, by_id))
                declared, assessed = overrated_parts(ranked, by_id)
                declared_part.append(declared)
                assessed_part.append(assessed)
                below.append(below_need_share(ranked, need, by_id))
                r = category_spearman(ranked, need, by_id)
                if r is not None:
                    rho.append(r)
        rows.append(Row(method, statistics.mean(nd), statistics.mean(pr), statistics.mean(ap),
                        statistics.mean(rho) if rho else None, statistics.mean(over) if over else None,
                        statistics.mean(below) if below else None,
                        bootstrap_ci(nd), bootstrap_ci(rho) if rho else None,
                        over_declared=statistics.mean(declared_part) if declared_part else None,
                        over_assessed=statistics.mean(assessed_part) if assessed_part else None,
                        p5=statistics.mean(pr5)))
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
             "| 95 % ДИ Спирмена | Завышенный грейд в топ-10 | Настоящий грейд ниже потребности |",
             "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {TITLES[r.method]} | {r.ndcg10:.3f} | {_ci(r.ndcg_ci)} | {r.p10:.3f} | {r.map:.3f} "
              f"| {_num(r.rho)} | {_ci(r.rho_ci)} | {_pct(r.overrated)} | {_pct(r.below_need)} |" for r in rows]
    lines += ["",
              "«Завышенный грейд в топ-10» — показанный грейд выше настоящего. "
              "«Настоящий грейд ниже потребности» — настоящее ниже грейда, который просит потребность; "
              "это второе определение завышения, его используют чужие работы."]
    return "\n".join(lines) + "\n"


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f} %"


def seeds_table(seeds: list[int], n_candidates: int, n_needs: int) -> tuple[str, dict[str, dict[str, float]]]:
    """The same benchmark on several seeds: mean and spread, so one lucky seed cannot carry a claim."""
    keys = ("bm25", "keyword", "full", "no_test", "no_fsp", "no_evidence")
    per: dict[str, dict[str, list[float]]] = {
        k: {"ndcg": [], "p10": [], "rho": [], "over": [], "below": [], "declared": [], "assessed": []}
        for k in keys
    }
    for sd in seeds:
        rows = {r.method: r for r in evaluate(make_dataset(n_candidates, n_needs, sd))}
        for k in keys:
            per[k]["ndcg"].append(rows[k].ndcg10)
            per[k]["p10"].append(rows[k].p10)
            per[k]["rho"].append(rows[k].rho if rows[k].rho is not None else float("nan"))
            per[k]["over"].append(rows[k].overrated or 0.0)
            per[k]["below"].append(rows[k].below_need or 0.0)
            per[k]["declared"].append(rows[k].over_declared or 0.0)
            per[k]["assessed"].append(rows[k].over_assessed or 0.0)

    def ms(xs: list[float], scale: float = 1.0, digits: int = 3) -> str:
        sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
        return f"{statistics.mean(xs) * scale:.{digits}f} ± {sd * scale:.{digits}f}"

    lines = [f"Зёрна {', '.join(map(str, seeds))}: среднее ± стандартное отклонение.", "",
             "| Ранжирование | nDCG@10 | P@10, оценка ≥ 2 | Спирмен внутри категории | Завышенный грейд в топ-10, % "
             "| Настоящий грейд ниже потребности, % |",
             "|---|---|---|---|---|---|"]
    lines += [f"| {TITLES[k].strip()} | {ms(per[k]['ndcg'])} | {ms(per[k]['p10'])} | {ms(per[k]['rho'])} "
              f"| {ms(per[k]['over'], 100, 1)} | {ms(per[k]['below'], 100, 1)} |"
              for k in keys]

    def part(method: str, key: str) -> str:
        return f"{statistics.mean(per[method][key]) * 100:.1f}"

    full_declared = part("full", "declared")
    full_assessed = part("full", "assessed")
    resume_declared = part("keyword", "declared")
    resume_assessed = part("keyword", "assessed")
    lines += ["",
              "Завышенный грейд в топ-10 по источнику показанного грейда, те же зерна. Порядок выдачи прежний. "
              f"Полная модель: заявлен {full_declared} %, подтверждён тестом {full_assessed} %. "
              f"По резюме: заявлен {resume_declared} %, подтверждён тестом {resume_assessed} %. "
              "Сумма двух долей совпадает со столбцом «Завышенный грейд»."]
    summary = {k: {m: statistics.mean(v) for m, v in per[k].items()} for k in keys}
    return "\n".join(lines) + "\n", summary


def load_pairs(path: str) -> dict:
    """JSONL of jury pairs: each line is need, candidate.observed and label 0..3.

    A JSON object in the same shape as --export is accepted too.
    """
    return parse_pairs(open(path, encoding="utf-8").read())


def parse_pairs(text: str) -> dict:
    """The body of a --pairs file: JSONL of pairs or one exported JSON object."""
    text = text.strip()
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


PUBLIC_MAX_PAIRS = 500
PUBLIC_METHODS = ("full", "keyword", "random")


def public_report(text: str) -> dict:
    """The same metrics as --pairs for the public page. ValueError carries the message for the person.

    Only labelled pairs are ranked: the page never reads the candidate bank.
    """
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        raise ValueError("Вставьте хотя бы одну пару: потребность, кандидат и оценка 0–3")
    if len(lines) > PUBLIC_MAX_PAIRS:
        raise ValueError(f"Не больше {PUBLIC_MAX_PAIRS} пар за раз")
    try:
        dataset = parse_pairs(text)
        for need in dataset["needs"]:
            _spec(need)
        for cand in dataset["candidates"]:
            _facts(cand)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Строка {exc.lineno}: это не JSON") from exc
    except ValueError as exc:
        raise ValueError("Оценка — целое от 0 до 3") from exc
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Не хватает поля {exc}: формат — как в примере") from exc
    if any(not 0 <= v <= 3 for labels in dataset["labels"].values() for v in labels.values()):
        raise ValueError("Оценка — целое от 0 до 3")
    judged = [n for n in dataset["needs"] if any(v >= 2 for v in dataset["labels"][n["id"]].values())]
    if not judged:
        raise ValueError("Нужна хотя бы одна потребность с кандидатом на оценку 2 или 3")
    rows = {row.method: row for row in evaluate(dataset)}
    pairs = sum(len(labels) for labels in dataset["labels"].values())
    from app.validation.per_need import paired_delta, per_need
    breakdown = per_need(dataset)
    return {
        "pairs": pairs, "needs": len(dataset["needs"]), "judged_needs": len(judged),
        "sha256": sha256(dataset),
        "rows": [{"method": m, "title": TITLES[m].strip(), "ndcg10": round(rows[m].ndcg10, 4),
                  "ndcg_ci": [round(v, 4) for v in rows[m].ndcg_ci] if rows[m].ndcg_ci else None,
                  "p10": round(rows[m].p10, 4), "p5": round(rows[m].p5, 4),
                  "map": round(rows[m].map, 4)} for m in PUBLIC_METHODS],
        "per_need": breakdown, "paired_delta": paired_delta(breakdown),
    }


# Thresholds of --check. They guard the claims in docs/VALIDATION_MATCHING.md, not a tuned optimum.
# Evidence guard: the test and the FSP axis each must raise the in-category Spearman. The rule is a sign,
# not a size: full minus the ablation, paired by need and pooled over GUARD_SEEDS, must have a 95 % bootstrap
# lower bound above zero (the same resampling as the paired nDCG table, 10 000 rounds).
GUARD_SEEDS = (2026, 2027, 2028)
GUARD_ABLATIONS = (("no_test", "без теста"), ("no_fsp", "без оси ФСП"))
NDCG_FLOOR = 0.65        # full model on the default seed; the release before the category order had 0.661


def evidence_guard(n_candidates: int, n_needs: int, seeds: tuple[int, ...] = GUARD_SEEDS) -> dict:
    """Per ablation: mean Δ Spearman per seed, and the pooled paired mean with its 95 % bootstrap interval."""
    out = {}
    for key, _ in GUARD_ABLATIONS:
        per_seed: dict[int, float] = {}
        pooled: list[float] = []
        for seed in seeds:
            curves = seed_curves(seed, n_candidates, n_needs)
            full, other = curves["rho"]["full"], curves["rho"][key]
            deltas = [a - b for a, b in zip(full, other, strict=True)]
            per_seed[seed] = statistics.mean(deltas) if deltas else float("nan")
            pooled.extend(deltas)
        mean, low, high = _paired_bounds(pooled, seed=11)
        out[key] = {"per_seed": per_seed, "mean": mean, "low": low, "high": high, "n": len(pooled)}
    return out


def guard_markdown(guard: dict) -> str:
    seeds = list(next(iter(guard.values()))["per_seed"]) if guard else []
    lines = [
        "Проверка доказательств: полная модель минус строка, Спирмен внутри категории, парно по потребностям. "
        "Сводный 95 % ДИ — бутстреп среднего по потребностям всех зёрен, 10 000 повторов. "
        "Проходит, если нижняя граница выше нуля.",
        "",
        "| Сравнение | " + " | ".join(f"Δ Спирмен, {s}" for s in seeds)
        + " | Сводно | 95 % ДИ | Потребностей | Проходит |",
        "|---|" + "---|" * len(seeds) + "---|---|---|---|",
    ]
    for key, title in GUARD_ABLATIONS:
        g = guard[key]
        cells = " | ".join(f"{g['per_seed'][s]:+.4f}" for s in seeds)
        lines.append(f"| {title} | {cells} | {g['mean']:+.4f} | {g['low']:+.4f}…{g['high']:+.4f} | {g['n']} "
                     f"| {'да' if g['low'] > 0 else 'нет'} |")
    lines.append("")
    return "\n".join(lines)


def checks_ok(rows: list[Row], synthetic: bool = True, guard: dict | None = None) -> list[str]:
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
    for ablation, _ in GUARD_ABLATIONS:
        if guard is None or not guard[ablation]["low"] > 0:
            failed.append(f"Spearman full - {ablation}: 95 % CI lower bound > 0 on seeds {GUARD_SEEDS}")
    if not (by["full"].overrated or 0.0) < (by["keyword"].overrated or 0.0):
        failed.append("overrated in top 10: full < keyword")
    return failed


def _print_tier_sweep(args: argparse.Namespace) -> None:
    """Three seeds for each tier width. The choice rule is printed, not applied."""
    from app.services import matching as matching_mod

    deltas = [float(part) for part in args.tier_delta.split(",") if part.strip()]
    saved = matching_mod.FIT_TIER_DELTA
    saved_flag = matching_mod.USE_FIT_TIERS
    matching_mod.USE_FIT_TIERS = True
    seeds = [args.seed + i for i in range(3)]
    print("Перебор ширины яруса. Условие: nDCG(полная) ≥ nDCG(без теста и без ФСП) − 0,005 "
          "на среднем трёх зёрен. Среди прошедших берётся наибольший Спирмен.")
    print(f"зёрна {', '.join(map(str, seeds))}, кандидатов {args.candidates}, потребностей {args.needs}")
    print("| Δ | nDCG полная | nDCG без теста и без ФСП | разница | Спирмен | завышенный грейд, % | проходит |")
    print("|---|---|---|---|---|---|---|")
    try:
        for delta in deltas:
            matching_mod.FIT_TIER_DELTA = delta
            nd_f, nd_e, rho, over = [], [], [], []
            for sd in seeds:
                rows = {r.method: r for r in evaluate(make_dataset(args.candidates, args.needs, sd))}
                nd_f.append(rows["full"].ndcg10)
                nd_e.append(rows["no_evidence"].ndcg10)
                rho.append(rows["full"].rho or 0.0)
                over.append(rows["full"].overrated or 0.0)
            mean_full = statistics.mean(nd_f)
            mean_bare = statistics.mean(nd_e)
            mean_rho = statistics.mean(rho)
            mean_over = statistics.mean(over)
            ok = mean_full >= mean_bare - 0.005
            print(f"| {delta:.2f} | {mean_full:.3f} | {mean_bare:.3f} | {mean_full - mean_bare:+.3f} "
                  f"| {mean_rho:.3f} | {mean_over * 100:.1f} | {'да' if ok else 'нет'} |")
    finally:
        matching_mod.FIT_TIER_DELTA = saved
        matching_mod.USE_FIT_TIERS = saved_flag


GRADE_RU = {"intern": "стажёр", "junior": "джуниор", "middle": "мидл", "senior": "сеньор", "lead": "лид"}
TRUST_RU = {"test_confirmed": "тест", "resume_confirmed": "резюме", "self_reported": "заявлено"}


def quadratic_weighted_kappa(left: list[int], right: list[int], cats: int = 4) -> float:
    """Quadratic weighted kappa. A miss of one grade costs less than a miss of three.

    κ_w = 1 − Σ w_ij·O_ij / Σ w_ij·E_ij, w_ij = (i − j)² / 9.
    """
    if len(left) != len(right) or not left:
        raise ValueError("kappa needs two equal non-empty lists")
    if any(v < 0 or v >= cats for v in (*left, *right)):
        raise ValueError("label out of 0..3")
    n = len(left)
    table = [[0.0] * cats for _ in range(cats)]
    for a, b in zip(left, right, strict=True):
        table[a][b] += 1.0
    row = [sum(table[i]) for i in range(cats)]
    col = [sum(table[i][j] for i in range(cats)) for j in range(cats)]
    num = den = 0.0
    for i in range(cats):
        for j in range(cats):
            weight = ((i - j) ** 2) / ((cats - 1) ** 2)
            num += weight * table[i][j]
            den += weight * row[i] * col[j] / n
    if den == 0.0:
        return 1.0
    return 1.0 - num / den


def blind_candidate_ids(dataset: dict, need: dict, rng: random.Random, per_need: int = 8) -> list[str]:
    """Three from the model top, three from the resume top, two at random. Then shuffle.

    A person already taken is skipped, so the eight cards are eight people. The shuffle hides
    which list a card came from.
    """
    model = rank(dataset, need, "full", rng)
    keyword = rank(dataset, need, "keyword", rng)
    picked: list[str] = []
    for cid in model:
        if len(picked) == 3:
            break
        picked.append(cid)
    taken = 0
    for cid in keyword:
        if cid in picked:
            continue
        picked.append(cid)
        taken += 1
        if taken == 3:
            break
    rest = [c["id"] for c in dataset["candidates"] if c["id"] not in picked]
    rng.shuffle(rest)
    picked.extend(rest[: max(0, per_need - len(picked))])
    rng.shuffle(picked)
    return picked[:per_need]


def _need_card(need: dict) -> str:
    from app.services.survey import SPECIALIZATIONS

    role = SPECIALIZATIONS.get(need.get("role"), need.get("role") or "не указана")
    grade = GRADE_RU.get(need.get("grade"), need.get("grade") or "не указан")
    skills = ", ".join(need.get("skills") or []) or "не названы"
    return f"Специализация: {role}. Грейд: {grade}. Навыки: {skills}"


def _candidate_card(observed: dict) -> str:
    from app.services.survey import INDUSTRIES, SPECIALIZATIONS

    role = SPECIALIZATIONS.get(observed.get("role"), observed.get("role") or "не указана")
    grade = GRADE_RU.get(observed.get("grade"), observed.get("grade") or "не указан")
    grade_line = f"{grade}, подтверждён тестом" if observed.get("grade_source") == "assessed" else f"{grade}, заявлен"
    skills = observed.get("skills") or {}
    skill_line = ", ".join(
        f"{name} ({TRUST_RU.get(level, level)})" for name, level in sorted(skills.items())) or "не указаны"
    if observed.get("test_n"):
        test_line = f"Тест: верных ответов {observed.get('test_correct')} из {observed['test_n']}"
    else:
        test_line = "Теста нет"
    lcb = observed.get("fsp_lcb")
    fsp_line = "Истории ФСП нет" if lcb is None else f"Ось ФСП, нижняя граница {lcb:.2f}"
    lines = [f"Специализация: {role}", f"Грейд: {grade_line}", f"Навыки: {skill_line}", test_line, fsp_line]
    industry = observed.get("industry")
    if industry and industry != "any":
        lines.append(f"Предметная область: {INDUSTRIES.get(industry, industry)}")
    return ". ".join(lines)


def write_blind_sheet(dataset: dict, path: str, per_need: int, rng: random.Random) -> int:
    """CSV the two raters fill in, plus a key with the same observed facts and no hidden truth."""
    by_id = {c["id"]: c for c in dataset["candidates"]}
    rows: list[dict] = []
    pairs: list[dict] = []
    for need in dataset["needs"]:
        for cid in blind_candidate_ids(dataset, need, rng, per_need):
            pair_id = f"p{len(rows) + 1:03d}"
            observed = by_id[cid]["observed"]
            rows.append({"pair_id": pair_id, "need": _need_card(need),
                         "candidate_card": _candidate_card(observed), "label": ""})
            pairs.append({
                "pair_id": pair_id,
                "need": {"id": need["id"], "role": need["role"], "grade": need["grade"], "skills": need["skills"]},
                "candidate_id": cid,
                "observed": observed,
            })
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["pair_id", "need", "candidate_card", "label"])
        writer.writeheader()
        writer.writerows(rows)
    key = str(Path(path).with_suffix(".key.json"))
    Path(key).write_text(json.dumps({"pairs": pairs}, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


def read_rater_labels(path: str) -> dict[str, int]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    labels: dict[str, int] = {}
    for row in rows:
        pair_id = (row.get("pair_id") or "").strip()
        raw = (row.get("label") or "").strip()
        if raw == "":
            raise SystemExit(f"Пустая оценка в {path}, пара {pair_id}")
        value = int(raw)
        if value not in (0, 1, 2, 3):
            raise SystemExit(f"Оценка вне 0…3 в {path}, пара {pair_id}")
        labels[pair_id] = value
    if not labels:
        raise SystemExit(f"В {path} нет строк")
    return labels


def merge_rater_labels(left: dict[str, int], right: dict[str, int], key: dict) -> list[dict]:
    """Floor of the mean of the two labels. 3 and 2 become 2; 3 and 0 become 1."""
    lines = []
    for pair in key["pairs"]:
        pair_id = pair["pair_id"]
        if pair_id not in left or pair_id not in right:
            raise SystemExit(f"Пары {pair_id} нет в одном из файлов")
        cid = pair["candidate_id"]
        lines.append({
            "need": pair["need"],
            "candidate_id": cid,
            "candidate": {"id": cid, "observed": pair["observed"]},
            "label": (left[pair_id] + right[pair_id]) // 2,
        })
    return lines


def _kappa_from_sheets(path_a: str, path_b: str) -> float:
    left = read_rater_labels(path_a)
    right = read_rater_labels(path_b)
    ids = sorted(set(left) | set(right))
    if set(left) != set(right):
        raise SystemExit("В двух файлах разные пары")
    return quadratic_weighted_kappa([left[i] for i in ids], [right[i] for i in ids])


def _print_overclaim(args: argparse.Namespace) -> None:
    rates = [float(part) for part in args.overclaim.split(",") if part.strip()]
    print(f"Доля заявивших грейд на ступень выше настоящего. Зерно {args.seed}, "
          f"{args.candidates} кандидатов, {args.needs} потребностей. Остальные заявляют истинный грейд.")
    print("| Доля | nDCG модели | nDCG по резюме | Спирмен модели | Спирмен по резюме | "
          "Завышенный грейд в топ-10, модель | Завышенный грейд в топ-10, по резюме |")
    print("|---|---|---|---|---|---|---|")
    for rate in rates:
        dataset = make_dataset(args.candidates, args.needs, args.seed, overclaim=rate)
        rows = {row.method: row for row in evaluate(dataset, args.seed)}
        full, resume = rows["full"], rows["keyword"]
        print(f"| {rate:.0%} | {full.ndcg10:.3f} | {resume.ndcg10:.3f} | {_num(full.rho)} | {_num(resume.rho)} | "
              f"{full.overrated:.1%} | {resume.overrated:.1%} |")


def seed_list(raw: str, start: int) -> list[int]:
    text = str(raw)
    if "," in text:
        return [int(part) for part in text.split(",") if part.strip()]
    count = int(text)
    return [start + i for i in range(count)] if count else []


def with_fsp_events(dataset: dict, seed: int) -> dict:
    """Replace the formula LCB with the production engine on fsp_axis.history().

    The random stream is not the one that built the people, so the public dataset without this
    step keeps its hash.
    """
    from app.services.scoring.engine import lcb_star
    from app.validation.fsp_axis import REF, history

    rng = random.Random(seed + 7919)
    for person in dataset["candidates"]:
        events = history(rng, float(person["truth"]["theta"]))
        if not events:
            person["observed"]["fsp_lcb"] = None
        else:
            person["observed"]["fsp_lcb"] = lcb_star(events, REF)["lcb"]
    return dataset


def _full_curves(dataset: dict) -> tuple[list[float], list[float | None]]:
    needs = [n for n in dataset["needs"] if any(v >= 2 for v in dataset["labels"][n["id"]].values())]
    by_id = {c["id"]: c for c in dataset["candidates"]}
    ndcg_values: list[float] = []
    rho_values: list[float | None] = []
    rng = random.Random(0)
    for need in needs:
        ranked = rank(dataset, need, "full", rng)
        ndcg_values.append(ndcg(ranked, dataset["labels"][need["id"]]))
        rho_values.append(category_spearman(ranked, need, by_id))
    return ndcg_values, rho_values


def _paired_bounds(deltas: list[float], seed: int = 11, rounds: int = 10000) -> tuple[float, float, float]:
    if not deltas:
        return float("nan"), float("nan"), float("nan")
    mean = statistics.mean(deltas)
    rng = random.Random(seed)
    n = len(deltas)
    means = sorted(statistics.mean(rng.choices(deltas, k=n)) for _ in range(rounds))
    return mean, means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]


def _print_pass_floor(seeds: list[int], n_candidates: int, n_needs: int) -> None:
    """Before/after for a floor under a passed grade. Public seeds are not used."""
    print("Полоса «Тест» у сдавшего на грейд потребности не ниже непроверенного. Новое минус старое.")
    print("| Зерно | Δ nDCG@10 | Δ Спирмен в категории |")
    print("|---|---|---|")
    nd_all: list[float] = []
    rho_all: list[float] = []
    try:
        for seed in seeds:
            dataset = make_dataset(n_candidates, n_needs, seed)
            matching_service.PASS_TEST_FLOOR = False
            old_nd, old_rho = _full_curves(dataset)
            matching_service.PASS_TEST_FLOOR = True
            new_nd, new_rho = _full_curves(dataset)
            nd_delta = [b - a for a, b in zip(old_nd, new_nd, strict=True)]
            rho_delta = [b - a for a, b in zip(old_rho, new_rho, strict=True) if a is not None and b is not None]
            nd_all.extend(nd_delta)
            rho_all.extend(rho_delta)
            rho_mean = statistics.mean(rho_delta) if rho_delta else float("nan")
            print(f"| {seed} | {statistics.mean(nd_delta):+.4f} | {rho_mean:+.4f} |", flush=True)
    finally:
        matching_service.PASS_TEST_FLOOR = False
    mean, low, high = _paired_bounds(nd_all)
    rho_mean = statistics.mean(rho_all) if rho_all else float("nan")
    print(f"Вместе: Δ nDCG@10 {mean:+.4f}, 95 % ДИ [{low:+.4f}; {high:+.4f}], Δ Спирмен {rho_mean:+.4f}")
    if low < -0.005 or rho_mean < 0:
        print("Порог не пройден. Пол в продукт не записывается.")
        raise SystemExit(1)
    print("Порог пройден.")


def _print_holdout(seeds: list[int], n_candidates: int, n_needs: int) -> None:
    """Before/after on holdout seeds. Before is the old average of test and FSP; after only lifts."""
    print("Отложенные зёрна, LCB из событий движка. Новое минус старое. Порядок «до» — среднее факторов.")
    print("| Зерно | Δ nDCG@10 | Δ Спирмен в категории |")
    print("|---|---|---|")
    nd_all: list[float] = []
    rho_all: list[float] = []
    for seed in seeds:
        dataset = with_fsp_events(make_dataset(n_candidates, n_needs, seed), seed)
        matching_service.FSP_LIFT = "mean"
        old_nd, old_rho = _full_curves(dataset)
        matching_service.FSP_LIFT = "boost"
        new_nd, new_rho = _full_curves(dataset)
        nd_delta = [b - a for a, b in zip(old_nd, new_nd, strict=True)]
        rho_delta = [b - a for a, b, in zip(old_rho, new_rho, strict=True) if a is not None and b is not None]
        nd_all.extend(nd_delta)
        rho_all.extend(rho_delta)
        rho_mean = statistics.mean(rho_delta) if rho_delta else float("nan")
        print(f"| {seed} | {statistics.mean(nd_delta):+.4f} | {rho_mean:+.4f} |")
    matching_service.FSP_LIFT = "boost"
    nd_mean, nd_low, nd_high = _paired_bounds(nd_all)
    rho_mean = statistics.mean(rho_all) if rho_all else float("nan")
    print(f"nDCG@10: {nd_mean:+.4f}, 95 % ДИ [{nd_low:+.4f}; {nd_high:+.4f}]")
    print(f"Спирмен в категории: {rho_mean:+.4f}")
    nd_ok = nd_low >= -0.005
    rho_ok = rho_mean >= -0.01
    print(f"нижняя граница nDCG ≥ −0,005: {'да' if nd_ok else 'нет'}")
    print(f"Спирмен ≥ −0,01: {'да' if rho_ok else 'нет'}")
    if not (nd_ok and rho_ok):
        raise SystemExit(1)


def main() -> None:
    global TEST_NOISE_SD
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidates", type=int, default=800)
    parser.add_argument("--needs", type=int, default=80)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--seeds", default="3",
                        help="how many consecutive seeds, or a comma-separated list")
    parser.add_argument("--fsp-events", action="store_true",
                        help="LCB from the scoring engine on contest histories; the public hash is without this")
    parser.add_argument("--holdout", action="store_true",
                        help="before/after on the holdout seeds, with contest histories")
    parser.add_argument("--pass-floor", action="store_true",
                        help="before/after for a floor under a passed grade; does not change the product")
    parser.add_argument("--order", choices=("score", "category_first"), default="score",
                        help="category_first measures a band before the score; it does not change the product")
    parser.add_argument("--export", help="write the generated dataset (with labels) to this JSON file")
    parser.add_argument("--import", dest="imported", help="evaluate a labelled dataset in the same JSON format")
    parser.add_argument("--pairs", help="JSONL of jury pairs: need, candidate, label 0..3")
    parser.add_argument("--test-noise", type=float, default=0.0,
                        help="SD of the measurement error of the simulated test θ; 0 is the published benchmark")
    parser.add_argument("--check", action="store_true", help="fail unless the thresholds in checks_ok hold")
    parser.add_argument("--ladder", action="store_true",
                        help="print only the base ladder (random, self-description, BM25, resume) and exit")
    parser.add_argument("--tier-delta", default="",
                        help="comma-separated tier widths; print the three-seed sweep and exit")
    parser.add_argument("--blind-export", help="CSV for two people: observed profile only, empty label column")
    parser.add_argument("--per-need", type=int, default=8, help="cards per need in --blind-export")
    parser.add_argument("--kappa", nargs=2, metavar=("A", "B"),
                        help="quadratic weighted kappa of two filled sheets")
    parser.add_argument("--merge-raters", nargs=2, metavar=("A", "B"),
                        help="floor of the mean of two sheets, written as JSONL for --pairs")
    parser.add_argument("--merged", help="where --merge-raters writes the JSONL")
    parser.add_argument("--stuffing", type=float, default=0.0,
                        help="share of candidates who declare every skill of their role; does not change the product")
    parser.add_argument("--unconfirmed", action="store_true",
                        help="show, demote or hide unconfirmed grades; does not change the product")
    parser.add_argument("--overclaim", default="",
                        help="comma-separated shares who declare one grade too high; print the curve and exit")
    parser.add_argument("--protocol", choices=("a", "b", "all"),
                        help="graded protocols of published methods (app.validation.protocols); print and exit")
    args = parser.parse_args()
    TEST_NOISE_SD = args.test_noise
    if args.protocol:
        import sys

        from app.validation import protocols
        sys.argv = [sys.argv[0], "--protocol", args.protocol]
        protocols.main()
        return
    global ORDER_MODEL
    ORDER_MODEL = args.order
    if args.ladder:
        print(ladder_markdown(ladder(seed_list(args.seeds, args.seed) or [args.seed], args.candidates, args.needs)))
        return
    if args.kappa:
        value = _kappa_from_sheets(args.kappa[0], args.kappa[1])
        print(f"взвешенная каппа {value:.2f} на парах из двух файлов")
        print(f"порог годности 0,6: {'да' if value >= 0.6 else 'нет'}")
        return
    if args.merge_raters:
        if not args.merged:
            raise SystemExit("Укажите --merged для файла JSONL")
        left = read_rater_labels(args.merge_raters[0])
        right = read_rater_labels(args.merge_raters[1])
        key_file = str(Path(args.merge_raters[0]).with_suffix(".key.json"))
        key = json.loads(Path(key_file).read_text(encoding="utf-8"))
        lines = merge_rater_labels(left, right, key)
        Path(args.merged).write_text(
            "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n", encoding="utf-8")
        print(f"слито {len(lines)} пар в {args.merged}")
        return
    if args.tier_delta:
        _print_tier_sweep(args)
        return
    if args.overclaim:
        _print_overclaim(args)
        return
    if args.stuffing:
        print(f"Накрутка навыков: {args.stuffing:.0%} кандидатов заявляют все навыки своей специализации. "
              f"Зерно {args.seed}, {args.candidates} кандидатов, {args.needs} потребностей.")
        print("| Метод | В топ-10 до накрутки | В топ-10 после (95 % ДИ) | В своей специализации "
              "| Отношение | nDCG@10 |")
        print("|---|---|---|---|---|---|")
        for r in stuffing_study(make_dataset(args.candidates, args.needs, args.seed), args.stuffing):
            def pct(x: float) -> str:
                return f"{x * 100:.1f} %".replace(".", ",")
            ci = f"{pct(r['top_ci'][0])}…{pct(r['top_ci'][1])}"
            print(f"| {r['method']} | {pct(r['before'])} | {pct(r['top'])} ({ci}) "
                  f"| {pct(r['pool'])} | {r['ratio']:.2f} | {r['ndcg']:.4f} |".replace(".", ","))
        return
    if args.unconfirmed:
        rows = unconfirmed_study(make_dataset(args.candidates, args.needs, args.seed))
        print(unconfirmed_markdown(rows, args.seed, args.candidates, args.needs))
        return
    if args.pass_floor:
        _print_pass_floor(seed_list(args.seeds, args.seed), args.candidates, args.needs)
        return
    if args.holdout or (args.fsp_events and "," in str(args.seeds)):
        seeds = list(HOLDOUT_SEEDS) if args.holdout else seed_list(args.seeds, args.seed)
        _print_holdout(seeds, args.candidates, args.needs)
        return
    if args.blind_export:
        dataset = make_dataset(args.candidates, args.needs, args.seed)
        count = write_blind_sheet(dataset, args.blind_export, args.per_need, random.Random(args.seed + 1))
        print(f"лист: {count} пар, {args.needs} потребностей, по {args.per_need} кандидатов, зерно {args.seed}")
        print("Оценку 0, 1, 2 или 3 двое ставят независимо в колонку label. Баллов подбора в листе нет.")
        return
    if args.pairs and args.imported:
        raise SystemExit("Укажите либо --pairs, либо --import")
    if args.pairs:
        dataset = load_pairs(args.pairs)
    elif args.imported:
        with open(args.imported, encoding="utf-8") as fh:
            dataset = json.load(fh)
    else:
        dataset = make_dataset(args.candidates, args.needs, args.seed)
        if args.fsp_events:
            dataset = with_fsp_events(dataset, args.seed)
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
        seeds = seed_list(args.seeds, args.seed)
        if seeds and not args.imported and not args.fsp_events:
            table, _ = seeds_table(seeds, args.candidates, args.needs)
            print()
            print(table)
        paired_seeds = seeds or [args.seed]
        if not args.imported and not args.fsp_events:
            print()
            print(paired_report(paired_seeds, args.candidates, args.needs))
            print(baseline_markdown(baseline_deltas(paired_seeds, args.candidates, args.needs)))
    print("sha256", sha256(dataset))
    if args.check:
        guard = None
        if synthetic and not args.imported:
            guard = evidence_guard(args.candidates, args.needs)
            print()
            print(guard_markdown(guard))
        failed = checks_ok(rows, synthetic, guard)
        print("checks:", "failed " + ", ".join(failed) if failed else "passed")
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()


__all__ = ["make_dataset", "evaluate", "relevance", "sha256", "Row", "asdict"]
