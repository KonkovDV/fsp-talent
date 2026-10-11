"""Validation of the adaptive test by simulation: `python -m app.validation.assessment [--n 3000] [--md out.md]`.

There is no labelled data in the hackathon (TZ section 2), so this is a parameter-recovery study run through
the production selector and decision code (app.services.cat). Simulated candidates have a known ability
θ ~ N(0.3, 1) and a declared grade: 60 % declare their true grade, 30 % one level higher, 10 % one lower.

The simulated "truth" is deliberately not the model the service assumes: every item key has its own true
difficulty shift N(0, 0.3²) and discrimination ×U(0.8, 1.2) that the service does not know (uncalibrated
bank). Guessing is c = 0.25 for items with four options and 0.02 for a typed whole number; an item is typed
with the share its generator really produces (app.items.registry.typed_share). So the numbers include misfit.

Scenarios:
  clean      no leak; also counts false leak alarms on clean data;
  choices    ablation: the same bank with four options on every item (the design before typed answers);
  leak       30 % of candidates know the answers of their specialization's main family (a published solver);
  monitored  the leak monitor ran on the "leak" answers, quarantined keys are excluded, a new cohort is tested.
Plus: retest agreement and Cohen's kappa, item discrimination, test length, item exposure, random guessing.
`--check` exits with an error when the clean scenario breaks the thresholds in CHECKS (run in CI).
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import math
import random
import statistics
import sys
from dataclasses import dataclass, field

from app.items import CHOICE_C, LEVEL_B, TYPED_C
from app.items.registry import FAMILIES, families_for, typed_share
from app.models.assessment import GRADE_ORDER
from app.services import cat as cat_module
from app.services.cat import (
    CUTS,
    MAX_ITEMS,
    PASS_P,
    Response,
    State,
    choose,
    decide,
    evaluate,
    item_key,
    lower_offer,
    p3,
    posterior,
    prev_grade,
)
from app.services.item_monitor import KeyStats, calibrate_offset, leave_family_out

# Настройка: тест 101..105, подбор 3001..3005.
# Отложенные, один прогон после фиксации кода: тест 201..205, подбор 4001..4005.
# Публичные 7 и 2026..2028 только печатают итог, на них ничего не подбирается.
HOLDOUT_SEEDS = (201, 202, 203, 204, 205)

# Who sits the published exam: every specialization, including data engineering.
SPECS = ("backend", "fullstack", "frontend", "mobile", "ml", "devops", "security", "embedded", "qa", "analyst", "data")
MAIN_FAMILY = {"backend": "py_eval", "fullstack": "js_eval", "frontend": "js_eval", "mobile": "js_eval",
               "ml": "ml_metrics", "devops": "net_ipv4", "security": "sec_decode", "embedded": "emb_bits",
               "qa": "qa_checks", "analyst": "analyst_metrics", "data": "data_batches"}


def true_grade(theta: float) -> str | None:
    grade = None
    for g in GRADE_ORDER:
        if theta >= CUTS[g]:
            grade = g
    return grade


@dataclass
class Truth:
    offsets: dict[str, float]
    a_mult: dict[str, float]

    @classmethod
    def draw(cls, rng: random.Random) -> Truth:
        offsets, mult = {}, {}
        for fam in FAMILIES.values():
            for level in fam.levels:
                key = item_key(fam, level)
                offsets[key] = rng.gauss(0.0, 0.3)
                mult[key] = rng.uniform(0.8, 1.2)
        return cls(offsets, mult)


@dataclass
class Session:
    spec: str
    target: str
    theta: float
    earned: str | None
    passed: bool
    recommended: str | None    # next grade recommended for a separate test (never assigned by this session)
    n: int
    keys: list[str]
    # key, family, a, b, c, correct
    answers: list[tuple[str, str, float, float, float, bool]] = field(default_factory=list)
    theta_hat: float = 0.0
    se: float = 1.0
    p_pass: float = 0.5
    lower_offer: str | None = None   # the grade below a failed target that the candidate may accept


_TYPED = True   # switched off by choices_only() for the ablation


@contextlib.contextmanager
def choices_only():
    """The ablation: every item has four options, and the selector knows it."""
    global _TYPED
    original = cat_module.expected_guess
    cat_module.expected_guess = lambda family_id, level: CHOICE_C
    _TYPED = False
    try:
        yield
    finally:
        cat_module.expected_guess = original
        _TYPED = True


def _p4(theta: float, a: float, b: float, c: float, d: float) -> float:
    return c + (d - c) / (1.0 + math.exp(-a * (theta - b)))


def _instance_key(family_id: str, level: int, item) -> tuple:
    """Family, level and the generated parameters.

    The query text alone is not enough: two SQL items can share a query and differ by the table.
    A concept item is the same instance when its static key (or the wording) matches.
    """
    return (family_id, level, item.static_key or item.stem, item.code)


def run_session(theta: float, spec: str, target: str, truth: Truth, rng: random.Random,
                leaked_family: str | None = None, blocked: set[str] | None = None,
                guesser: bool = False, offsets: dict[str, float] | None = None,
                attack: str | None = None, collision: dict[str, float] | None = None,
                exposure: dict[str, float] | None = None,
                misspec: tuple[float, float] | None = None,
                control: dict[str, float] | None = None,
                known: set[tuple] | None = None, remember: set[tuple] | None = None) -> Session:
    state = State(spec=spec, target=target)
    keys: list[str] = []
    answers = []
    while True:
        verdict = evaluate(state)
        if verdict.stop_reason == "extend" and not state.extended:
            state.extended = True
            continue
        if verdict.done:
            break
        try:
            ch = choose(state, rng, offsets=offsets, blocked=blocked, exposure=exposure, control=control)
        except LookupError:
            # The same selector has nothing left. The extra six are a cap, not a promise.
            if not state.extended:
                raise
            break
        key = item_key(ch.family, ch.level)
        typed = _TYPED and rng.random() < typed_share(ch.family.id, ch.level)
        c = TYPED_C if typed else CHOICE_C
        item = None
        if known is not None or remember is not None:
            try:
                item = ch.family.generate(rng, ch.level, spec)
            except LookupError:
                item = None
        seen = _instance_key(ch.family.id, ch.level, item) if item is not None else None
        if remember is not None and seen is not None:
            remember.add(seen)
        if attack == "fixed":
            correct = True
        elif known is not None and seen is not None and seen in known:
            correct = True
        elif attack == "transfer":
            correct = rng.random() < (collision or {}).get(ch.family.id, 0.0)
        elif guesser:
            correct = rng.random() < c
        elif leaked_family and ch.family.id == leaked_family:
            correct = True
        elif misspec is not None:
            sigma_a, sigma_b = misspec
            a_star = ch.a * math.exp(rng.gauss(0.0, sigma_a))
            b_star = ch.b + rng.gauss(0.0, sigma_b)
            d_star = 0.95
            c_star = min(c + rng.uniform(0.0, 0.1), d_star - 0.01)
            correct = rng.random() < _p4(theta, a_star, b_star, c_star, d_star)
        else:
            p_true = p3(theta, ch.a * truth.a_mult[key], LEVEL_B[ch.level] + truth.offsets[key], c)
            correct = rng.random() < p_true
        state.responses.append(Response(ch.a, ch.b, c, correct, ch.family.id))
        state.families_used[ch.family.id] += 1
        state.topics_used[ch.family.topic] += 1
        state.concept_used += ch.family.kind == "concept"
        keys.append(key)
        answers.append((key, ch.family.id, ch.a, ch.b, c, correct))
    out = decide(state)
    offer = lower_offer(state, out)
    s = Session(spec, target, theta, out.earned, out.passed, out.recommend_next, state.n, keys, answers,
                out.theta, out.se, out.p_pass, offer[0] if offer else None)
    return s


def _declared(theta: float, rng: random.Random) -> str:
    g = true_grade(theta) or "junior"
    i = GRADE_ORDER.index(g)
    r = rng.random()
    if r < 0.30:
        i = min(i + 1, len(GRADE_ORDER) - 1)
    elif r < 0.40:
        i = max(i - 1, 0)
    return GRADE_ORDER[i]


@dataclass
class CohortReport:
    n: int
    accuracy: float            # pass/fail matches truth (θ ≥ cut of declared grade)
    accuracy_clear: float      # the same for candidates more than 0.5 from the cut (one grade band is 1.0)
    sensitivity: float         # pass rate of those truly at or above the declared grade
    false_pass: float          # pass rate of those truly below the declared grade
    false_recommend: float     # a test at the next grade recommended although θ < its cut (share of all sessions)
    mean_len: float
    p90_len: float
    stopped_early: float       # share of sessions decided before MAX_ITEMS
    max_exposure: float        # highest share of sessions that served one item key, over every specialization
    spec_max_exposure: float   # the same share inside one specialization, the highest of the eleven
    concept_share: float
    exact_grade: float         # earned grade equals the true grade (None counts)
    within_one: float          # earned grade is at most one step from the truth
    overgrade: float           # earned grade is strictly above the truth


Person = tuple[float, str, str]   # true ability, specialization, declared grade


def population(n: int, rng: random.Random) -> list[Person]:
    """Candidates are drawn apart from their answers, so two designs can be compared on the same people."""
    people = []
    for _ in range(n):
        theta = rng.gauss(0.3, 1.0)
        people.append((theta, rng.choice(SPECS), _declared(theta, rng)))
    return people


def cohort(people: list[Person], truth: Truth, rng: random.Random, leak_share: float = 0.0,
           blocked: set[str] | None = None, offsets: dict[str, float] | None = None,
           stream: int | None = None, misspec: tuple[float, float] | None = None,
           by_spec: bool = False, control: dict[str, float] | None = None,
           ) -> tuple[CohortReport, list[Session]]:
    """`stream` gives every person an own random stream: two designs then differ only by the design
    (the same people leak, the same answers fall the same way until the item sequences part)."""
    sessions = []
    seen: collections.Counter[str] = collections.Counter()
    spec_seen: dict[str, collections.Counter[str]] = {}
    spec_n: dict[str, int] = {}
    for index, (theta, spec, target) in enumerate(people):
        if stream is not None:
            rng = random.Random(stream * 1_000_003 + index)
        leaked = MAIN_FAMILY[spec] if rng.random() < leak_share else None
        # The live bank starts Sympson–Hetter after the same warm-up the selector uses.
        if by_spec:
            n_here = spec_n.get(spec, 0)
            bucket = spec_seen.get(spec)
            rates = {key: count / n_here for key, count in bucket.items()} if bucket and n_here >= 20 else None
        else:
            rates = {key: count / index for key, count in seen.items()} if index >= 20 else None
        session = run_session(theta, spec, target, truth, rng, leaked, blocked, offsets=offsets,
                              exposure=rates, misspec=misspec, control=control)
        seen.update(set(session.keys))
        if by_spec:
            spec_seen.setdefault(spec, collections.Counter()).update(set(session.keys))
            spec_n[spec] = spec_n.get(spec, 0) + 1
        sessions.append(session)
    n = len(sessions)
    right = sum(s.passed == (s.theta >= CUTS[s.target]) for s in sessions)
    clear = [s for s in sessions if abs(s.theta - CUTS[s.target]) > 0.5]
    above = [s for s in sessions if s.theta >= CUTS[s.target]]
    below = [s for s in sessions if s.theta < CUTS[s.target]]
    false_rec = sum(1 for s in sessions if s.recommended and s.theta < CUTS[s.recommended])
    lengths = sorted(s.n for s in sessions)
    exposure = collections.Counter(k for s in sessions for k in set(s.keys))
    concept = sum(1 for s in sessions for k in s.keys if FAMILIES[k.split(":")[0]].kind == "concept")

    def _idx(grade: str | None) -> int | None:
        return GRADE_ORDER.index(grade) if grade in GRADE_ORDER else None

    exact = within = over = 0
    for s in sessions:
        truth_g = true_grade(s.theta)
        ti, ei = _idx(truth_g), _idx(s.earned)
        exact += s.earned == truth_g
        if ti is None and ei is None or (ti is not None and ei is not None and abs(ti - ei) <= 1):
            within += 1
        if ei is not None and (ti is None or ei > ti):
            over += 1
    return CohortReport(
        n=n, accuracy=right / n,
        accuracy_clear=sum(s.passed == (s.theta >= CUTS[s.target]) for s in clear) / max(1, len(clear)),
        sensitivity=sum(s.passed for s in above) / max(1, len(above)),
        false_pass=sum(s.passed for s in below) / max(1, len(below)),
        false_recommend=false_rec / n, mean_len=statistics.mean(lengths),
        p90_len=lengths[int(0.9 * (len(lengths) - 1))],
        stopped_early=sum(s.n < MAX_ITEMS for s in sessions) / n,
        max_exposure=max(exposure.values()) / n,
        spec_max_exposure=_spec_max(sessions),
        concept_share=concept / sum(lengths),
        exact_grade=exact / n, within_one=within / n, overgrade=over / n,
    ), sessions


def monitor(sessions: list[Session]) -> dict[str, KeyStats]:
    stats: dict[str, KeyStats] = collections.defaultdict(KeyStats)
    for s in sessions:
        for key, p, correct in leave_family_out(s.answers, CUTS[s.target]):
            stats[key].add(p, correct)
    return stats


def _rest_rows(sessions: list[Session]) -> dict[str, list[tuple[float, float, float, float, bool]]]:
    """Per key: (ability estimated without the key's family, a, b, c, correct). The item's own family is
    left out, so a leaked or easy family does not inflate the ability it is compared with."""
    rows: dict[str, list] = collections.defaultdict(list)
    for s in sessions:
        for fam in {r[1] for r in s.answers}:
            others = [Response(a, b, c, ok) for _, f, a, b, c, ok in s.answers if f != fam]
            theta = posterior(others, prior_mean=CUTS[s.target]).theta
            for key, f, a, b, c, ok in s.answers:
                if f == fam:
                    rows[key].append((theta, a, b, c, ok))
    return rows


def calibrate(sessions: list[Session]) -> dict[str, float]:
    """Per-key difficulty shift from a pretest cohort, with ability estimated without the key's family."""
    return {k: calibrate_offset(v) for k, v in _rest_rows(sessions).items() if len(v) >= 30}


@dataclass
class Discrimination:
    """How well items separate stronger and weaker candidates, for one answer format."""
    keys: int                  # item keys with at least 30 answers in this format
    median_r: float            # median point-biserial r between "correct" and the rest-of-test ability
    good_share: float          # share of keys with r ≥ 0.20 (the usual floor for a working item)
    weak_right: float          # right answers of candidates 0.5+ below the item's difficulty
    strong_right: float        # right answers of candidates 0.5+ above it


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return 0.0
    return statistics.correlation(xs, ys)


def discrimination(sessions: list[Session]) -> dict[str, Discrimination]:
    by_mode: dict[str, dict[str, list]] = {"typed": collections.defaultdict(list),
                                           "choice": collections.defaultdict(list)}
    for key, rows in _rest_rows(sessions).items():
        for row in rows:
            by_mode["typed" if row[3] < CHOICE_C else "choice"][key].append(row)
    out = {}
    for mode, keys in by_mode.items():
        rs = [_pearson([t for t, *_ in v], [float(ok) for *_, ok in v]) for v in keys.values() if len(v) >= 30]
        rows = [row for v in keys.values() for row in v]
        weak = [ok for t, _, b, _, ok in rows if t <= b - 0.5]
        strong = [ok for t, _, b, _, ok in rows if t >= b + 0.5]
        out[mode] = Discrimination(
            keys=len(rs), median_r=statistics.median(rs) if rs else 0.0,
            good_share=sum(r >= 0.20 for r in rs) / max(1, len(rs)),
            weak_right=sum(weak) / max(1, len(weak)), strong_right=sum(strong) / max(1, len(strong)),
        )
    return out


@dataclass
class Retest:
    """The same candidate takes the test twice, with fresh items (TZ: stability on a repeated attempt)."""
    pairs: int
    agreement: float           # same pass/fail
    kappa: float               # Cohen's kappa of pass/fail: agreement beyond what the pass rate gives by chance
    agreement_clear: float     # pairs more than 0.5 from the cut
    same_grade: float          # same confirmed grade (a test confirms only its target, or nothing)
    theta_r: float             # correlation of the two ability estimates
    weighted_kappa: float      # quadratic weighted kappa of the two earned grades
    own_overlap: float = 0.0   # share of the second test's item keys the same person already saw in the first
    decision_consistency: float = 0.0  # predicted repeat agreement at the product's 0.75 rule
    # NEW-2: the band is what the first test itself can see, |θ̂ − cut| / SE < 1 ("borderline").
    borderline_share: float = 0.0
    agreement_confident: float = 1.0
    agreement_confident_ci: tuple[float, float] = (1.0, 1.0)
    agreement_borderline: float = 1.0


BAND_Z = 1.0   # |θ̂ − cut| / SE below this is "on the border": the decision is shown with a mark


def borderline(session: Session) -> bool:
    """Observable at decision time: the estimate sits within one standard error of the target's cut."""
    return abs(session.theta_hat - CUTS[session.target]) < BAND_Z * max(session.se, 1e-9)


def _bootstrap_ci(flags: list[bool], seed: int = 2026, draws: int = 2000) -> tuple[float, float]:
    """Percentile bootstrap 95 % interval of a share. Fixed seed: the report is reproducible."""
    if not flags:
        return (1.0, 1.0)
    rng = random.Random(seed)
    n = len(flags)
    means = sorted(sum(flags[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return (means[int(0.025 * draws)], means[int(0.975 * draws) - 1])


def retest(people: list[Person], truth: Truth, rng: random.Random, offsets: dict[str, float],
           misspec: tuple[float, float] | None = None) -> Retest:
    pairs = [(theta, target,
              run_session(theta, spec, target, truth, rng, offsets=offsets, misspec=misspec),
              run_session(theta, spec, target, truth, rng, offsets=offsets, misspec=misspec))
             for theta, spec, target in people]
    agree = [a.passed == b.passed for _, _, a, b in pairs]
    p1 = statistics.mean(a.passed for _, _, a, _ in pairs)
    p2 = statistics.mean(b.passed for _, _, _, b in pairs)
    po, pe = statistics.mean(agree), p1 * p2 + (1 - p1) * (1 - p2)
    clear = [ok for (theta, target, _, _), ok in zip(pairs, agree, strict=True) if abs(theta - CUTS[target]) > 0.5]
    band = [borderline(a) for _, _, a, _ in pairs]
    confident = [ok for ok, b in zip(agree, band, strict=True) if not b]
    edge = [ok for ok, b in zip(agree, band, strict=True) if b]
    return Retest(
        borderline_share=statistics.mean(band) if band else 0.0,
        agreement_confident=statistics.mean(confident) if confident else 1.0,
        agreement_confident_ci=_bootstrap_ci(confident),
        agreement_borderline=statistics.mean(edge) if edge else 1.0,
        pairs=len(pairs), agreement=po, kappa=(po - pe) / (1 - pe) if pe < 1 else 1.0,
        decision_consistency=_decision_consistency([a for _, _, a, _ in pairs]),
        agreement_clear=statistics.mean(clear) if clear else 1.0,
        same_grade=statistics.mean(a.earned == b.earned for _, _, a, b in pairs),
        theta_r=_pearson([a.theta_hat for _, _, a, _ in pairs], [b.theta_hat for _, _, _, b in pairs]),
        weighted_kappa=_quadratic_kappa([a.earned for _, _, a, _ in pairs],
                                        [b.earned for _, _, _, b in pairs]),
        own_overlap=statistics.mean(len(set(a.keys) & set(b.keys)) / max(1, len(set(b.keys)))
                                    for _, _, a, b in pairs),
    )


def _quadratic_kappa(xs: list[str | None], ys: list[str | None]) -> float:
    """Quadratic weighted kappa. A miss by two grades costs more than a miss by one."""
    labels: list[str | None] = [*GRADE_ORDER, None]
    index = {g: i for i, g in enumerate(labels)}
    k = len(labels)
    n = len(xs)
    if n == 0:
        return 1.0
    obs = [[0] * k for _ in range(k)]
    for a, b in zip(xs, ys, strict=True):
        obs[index[a]][index[b]] += 1
    row = [sum(obs[i]) for i in range(k)]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    weight = [[((i - j) / (k - 1)) ** 2 for j in range(k)] for i in range(k)]
    po = sum(weight[i][j] * obs[i][j] for i in range(k) for j in range(k)) / n
    pe = sum(weight[i][j] * row[i] * col[j] for i in range(k) for j in range(k)) / (n * n)
    if pe == 0:
        return 1.0
    return 1.0 - po / pe


@dataclass
class Report:
    ladder: dict[str, tuple[int, float]]   # true grade -> (people, share who passed the middle test)
    clean: CohortReport
    choices: CohortReport
    leak: CohortReport
    monitored: CohortReport
    false_alarms_clean: int
    keys_clean: int
    leaked_keys: int
    leaked_flagged: int
    other_flagged: int
    retest: Retest
    retest_choices: Retest
    discrimination: dict[str, Discrimination]
    typed_share: float
    guesser_pass: float
    guesser_pass_choices: float
    blocked: list[str]
    transfer_pass: float
    fixed_pass: float
    cusum_leaked: int
    cusum_false_clean: int
    mae_a_before: float
    mae_a_after: float
    topic_false_pass: float
    topic_accuracy: float
    rudner_accuracy: float
    rudner_consistency: float
    posterior_accuracy: float
    grade_matrix: list[list[int]]
    overlap: float
    region_peaks: list[float]
    path: PathStudy | None = None
    misspec: list[MisspecRow] = field(default_factory=list)
    fixed_form: FixedForm | None = None
    stolen: StolenSessions | None = None
    multiclass_accuracy: float = 0.0
    ece: float = 0.0
    reliability: list[tuple[int, float, float]] = field(default_factory=list)
    spec_rows: list[tuple[str, float, str, int]] = field(default_factory=list)
    overlap_spec: float = 0.0
    adjacent_auc: list[AdjacentAuc] = field(default_factory=list)


@dataclass
class AdjacentAuc:
    lower: str
    upper: str
    n_lower: int
    n_upper: int
    auc: float
    ci: tuple[float, float]


def auc(lower: list[float], upper: list[float]) -> float:
    """P(score of an upper-grade candidate > score of a lower-grade one), ties count one half.

    Mann–Whitney U / (n₁·n₂) through ranks, O(n log n). Hanley & McNeil 1982, doi:10.1148/radiology.143.1.7063747.
    """
    if not lower or not upper:
        return float("nan")
    pooled = sorted([(x, 0) for x in lower] + [(x, 1) for x in upper])
    rank_sum = 0.0
    i = 0
    while i < len(pooled):
        j = i
        while j < len(pooled) and pooled[j][0] == pooled[i][0]:
            j += 1
        mid = (i + j + 1) / 2   # average 1-based rank of the tied run
        rank_sum += mid * sum(1 for k in range(i, j) if pooled[k][1] == 1)
        i = j
    n1, n2 = len(upper), len(lower)
    return (rank_sum - n1 * (n1 + 1) / 2) / (n1 * n2)


def adjacent_auc(sessions: list[Session], draws: int = 1000, seed: int = 2026,
                 min_n: int = 20) -> list[AdjacentAuc]:
    """How well θ̂ separates neighbouring true grades. 95 % CI: percentile bootstrap stratified by grade.

    Each grade is resampled on its own, so both group sizes stay fixed (Efron & Tibshirani 1993, ch. 13).
    Pairs with fewer than `min_n` people in a group are skipped.
    """
    by_grade: dict[str, list[float]] = {}
    for s in sessions:
        g = true_grade(s.theta)
        if g is not None:
            by_grade.setdefault(g, []).append(s.theta_hat)
    rng = random.Random(seed)
    rows: list[AdjacentAuc] = []
    for lo, hi in zip(GRADE_ORDER, GRADE_ORDER[1:]):
        a, b = by_grade.get(lo, []), by_grade.get(hi, [])
        if len(a) < min_n or len(b) < min_n:
            continue
        boot = sorted(auc([a[rng.randrange(len(a))] for _ in a], [b[rng.randrange(len(b))] for _ in b])
                      for _ in range(draws))
        ci = (boot[int(0.025 * draws)], boot[int(0.975 * draws) - 1]) if draws else (float("nan"),) * 2
        rows.append(AdjacentAuc(lo, hi, len(a), len(b), auc(a, b), ci))
    return rows


def _collision_rates(rng: random.Random, pairs: int = 4) -> dict[str, float]:
    """How often two fresh items of one family share an answer. A transferred key is right only then."""
    rates: dict[str, float] = {}
    for fam in FAMILIES.values():
        if fam.kind != "code":
            continue
        spec = next(iter(fam.specs))
        same = total = 0
        for level in fam.levels:
            if not fam.available(spec, level):
                continue
            for _ in range(pairs):
                left = fam.generate(random.Random(rng.randrange(1, 2**30)), level, spec)
                right = fam.generate(random.Random(rng.randrange(1, 2**30)), level, spec)
                total += 1
                same += left.options[left.correct] == right.options[right.correct]
        if total:
            rates[fam.id] = same / total
    return rates


def _attack_pass(people: list[Person], truth: Truth, rng: random.Random, offsets: dict[str, float],
                 rates: dict[str, float], fixed: bool) -> float:
    attack = "fixed" if fixed else "transfer"
    sessions = [run_session(theta, spec, target, truth, rng, offsets=offsets, attack=attack, collision=rates)
                for theta, spec, target in people]
    return sum(s.passed for s in sessions) / max(1, len(sessions))


def _discrimination_mae(sessions: list[Session], truth: Truth) -> tuple[float, float]:
    from app.services.item_monitor import calibrate_discrimination

    before, after = [], []
    for key, rows in _rest_rows(sessions).items():
        if len(rows) < 30 or key not in truth.a_mult:
            continue
        fam = FAMILIES[key.split(":")[0]]
        true_a = fam.a * truth.a_mult[key]
        before.append(abs(fam.a - true_a))
        # b in the row is already the difficulty the selector served (nominal plus pretest shift).
        est = calibrate_discrimination([(t, b, c, ok) for t, _a, b, c, ok in rows], a0=fam.a)
        after.append(abs(est - true_a))
    if not before:
        return 0.0, 0.0
    return statistics.mean(before), statistics.mean(after)


def _topic_shares(session: Session) -> dict[str, tuple[int, int]]:
    topics: dict[str, tuple[int, int]] = {}
    for _key, fam, *_rest, ok in session.answers:
        topic = FAMILIES[fam].topic
        n, right = topics.get(topic, (0, 0))
        topics[topic] = (n + 1, right + int(ok))
    return topics


def _topic_floor_effect(sessions: list[Session]) -> tuple[float, float]:
    """Accuracy and false-pass if a weak topic blocked an otherwise accepted grade. Not applied in the product yet."""
    from app.services.cat import topic_fails

    right = below_pass = below_n = 0
    for s in sessions:
        passed = s.passed and not topic_fails(_topic_shares(s))
        right += passed == (s.theta >= CUTS[s.target])
        if s.theta < CUTS[s.target]:
            below_n += 1
            below_pass += int(passed)
    n = max(1, len(sessions))
    return right / n, below_pass / max(1, below_n)


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


MATRIX_LABELS = ("ниже", *GRADE_ORDER)


def grade_matrix(sessions: list[Session]) -> list[list[int]]:
    """Counts of true grade (from θ) by the grade the session assigned. «ниже» is below intern, or no grade."""
    index = {name: i for i, name in enumerate(MATRIX_LABELS)}
    grid = [[0 for _ in MATRIX_LABELS] for _ in MATRIX_LABELS]
    for session in sessions:
        row = index[true_grade(session.theta) or "ниже"]
        col = index[session.earned or "ниже"]
        grid[row][col] += 1
    return grid


def _by_spec(sessions: list[Session]) -> dict[str, list[Session]]:
    grouped: dict[str, list[Session]] = {}
    for session in sessions:
        grouped.setdefault(session.spec, []).append(session)
    return grouped


def spec_exposure(sessions: list[Session]) -> list[tuple[str, float, str, int]]:
    """Max key share inside each specialization: (spec, share, key, people)."""
    rows = []
    for spec, group in sorted(_by_spec(sessions).items()):
        counts = collections.Counter(key for session in group for key in set(session.keys))
        key, count = counts.most_common(1)[0]
        rows.append((spec, count / len(group), key, len(group)))
    return rows


def _spec_max(sessions: list[Session]) -> float:
    rows = spec_exposure(sessions)
    return max((share for _, share, _, _ in rows), default=0.0)


def overlap_within_spec(sessions: list[Session]) -> float:
    """Mean, over sessions, of how often another session of the same specialization saw the same key."""
    total = used = 0.0
    for group in _by_spec(sessions).values():
        n = len(group)
        if n < 2:
            continue
        freq = collections.Counter(key for session in group for key in set(session.keys))
        for session in group:
            keys = set(session.keys)
            if not keys:
                continue
            total += sum(freq[key] - 1 for key in keys) / (len(keys) * (n - 1))
            used += 1
    return total / used if used else 0.0


def region_exposure(sessions: list[Session], seed: int) -> list[float]:
    """Max share of one item key inside each of four hidden groups.

    The group label comes from its own generator. The item selector never receives it,
    so a gap between groups is sampling noise.
    """
    labels = ("1", "2", "3", "4")
    rng = random.Random(seed)
    groups: dict[str, list[Session]] = {label: [] for label in labels}
    for session in sessions:
        groups[rng.choice(labels)].append(session)
    peaks: list[float] = []
    for group in groups.values():
        if not group:
            peaks.append(0.0)
            continue
        counts = collections.Counter(key for session in group for key in set(session.keys))
        peaks.append(max(counts.values()) / len(group))
    return peaks


def item_overlap(sessions: list[Session]) -> float:
    """Mean share of a candidate's items that another candidate in the same run also saw."""
    freq: collections.Counter[str] = collections.Counter(key for session in sessions for key in set(session.keys))
    n = len(sessions)
    if n < 2:
        return 0.0
    total = used = 0.0
    for session in sessions:
        keys = set(session.keys)
        if not keys:
            continue
        total += sum(freq[key] - 1 for key in keys) / len(keys)
        used += 1
    return total / used / (n - 1) if used else 0.0


def rudner(sessions: list[Session]) -> tuple[float, float, float]:
    """Classification accuracy at the declared-grade cut.

    Rudner (2001) treats θ̂ as normal with the posterior SD and averages the probability of the
    assigned side of the cut. Consistency is the average of p² + (1−p)². The third number is the
    same accuracy from the grid posterior the product actually uses, not from the normal approximation.
    """
    rudner_acc, consistency, posterior = [], [], []
    for s in sessions:
        se = max(s.se, 1e-3)
        p_above = 1.0 - _phi((CUTS[s.target] - s.theta_hat) / se)
        assigned = p_above if s.passed else 1.0 - p_above
        rudner_acc.append(assigned)
        consistency.append(p_above * p_above + (1.0 - p_above) ** 2)
        posterior.append(s.p_pass if s.passed else 1.0 - s.p_pass)
    n = max(1, len(sessions))
    return sum(rudner_acc) / n, sum(consistency) / n, sum(posterior) / n


def _inv_phi(p: float) -> float:
    """Inverse of the standard normal cdf. Eight Newton steps are exact for the pass threshold."""
    z = 0.0
    for _ in range(8):
        density = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
        z -= (_phi(z) - p) / density
    return z


# The product passes when θ̂ ≥ cut + z·SE. At PASS_P = 0.75, z = 0.6745.
_Z_PASS = _inv_phi(PASS_P)


def _decision_consistency(sessions: list[Session]) -> float:
    """P(the same pass/fail on an independent repeat), using the product's threshold, not the cut itself."""
    if not sessions:
        return 0.0
    total = 0.0
    for s in sessions:
        se = max(s.se, 1e-3)
        threshold = CUTS[s.target] + _Z_PASS * se
        q = _phi((s.theta_hat - threshold) / (math.sqrt(2.0) * se))
        total += q if s.passed else 1.0 - q
    return total / len(sessions)


def _class_edges() -> list[float]:
    return [-math.inf, *(CUTS[g] for g in GRADE_ORDER), math.inf]


def multiclass_rudner(sessions: list[Session]) -> float:
    """Mean probability of the true grade class under N(θ̂, SE²). Six classes, from below intern to lead."""
    if not sessions:
        return 0.0
    edges = _class_edges()
    total = 0.0
    for s in sessions:
        se = max(s.se, 1e-3)
        truth_g = true_grade(s.theta)
        k = 0 if truth_g is None else GRADE_ORDER.index(truth_g) + 1
        total += _phi((edges[k + 1] - s.theta_hat) / se) - _phi((edges[k] - s.theta_hat) / se)
    return total / len(sessions)


def reliability_curve(sessions: list[Session]) -> tuple[float, list[tuple[int, float, float]]]:
    """Ten bins of p_pass. ECE is the weighted gap between the stated probability and θ ≥ cut."""
    counts = [0] * 10
    stated = [0.0] * 10
    observed = [0.0] * 10
    for s in sessions:
        p = min(1.0, max(0.0, s.p_pass))
        bin_index = min(9, int(p * 10))
        counts[bin_index] += 1
        stated[bin_index] += p
        observed[bin_index] += 1.0 if s.theta >= CUTS[s.target] else 0.0
    rows: list[tuple[int, float, float]] = []
    ece = 0.0
    n = max(1, len(sessions))
    for i in range(10):
        if counts[i] == 0:
            rows.append((0, 0.0, 0.0))
            continue
        mean_p = stated[i] / counts[i]
        rate = observed[i] / counts[i]
        rows.append((counts[i], mean_p, rate))
        ece += counts[i] / n * abs(mean_p - rate)
    return ece, rows


def _guessers(truth: Truth, rng: random.Random) -> float:
    guess = [run_session(0.0, rng.choice(SPECS), rng.choice(GRADE_ORDER), truth, rng, guesser=True)
             for _ in range(300)]
    return sum(s.passed for s in guess) / len(guess)


@dataclass
class PathStudy:
    """The grade a person ends with after the product's own sequence of tests, not after one session."""
    n: int
    exact: float
    within_one: float
    over: float
    under: float
    unconfirmed: float
    mean_sessions: float
    mean_items: float
    again_exact: float
    again_within: float
    again_over: float
    again_under: float
    again_unconfirmed: float
    again_sessions: float
    again_items: float
    kappa: float
    weighted_kappa: float
    matrix: list[list[int]]
    # Same people as the first path. Shares are among that group; a missing grade is not "under".
    lower_n: int = 0
    lower_under: float = 0.0
    upper_n: int = 0
    upper_under: float = 0.0
    below_n: int = 0
    below_under: float = 0.0
    equal_n: int = 0
    equal_under: float = 0.0
    above_n: int = 0
    above_under: float = 0.0
    pass_curve: list[tuple[float, int, float]] = field(default_factory=list)
    half_shift: float | None = None


@dataclass
class MisspecRow:
    sigma_a: float
    sigma_b: float
    accuracy_clear: float
    false_pass: float
    kappa: float


@dataclass
class FixedForm:
    items: int
    people: int
    median_r: float
    good_share: float


@dataclass
class StolenSessions:
    n: int
    honest: float
    stolen: float
    fixed: float


def simulate_path(theta: float, spec: str, declared: str, truth: Truth, rng: random.Random,
                  offsets: dict[str, float] | None = None):
    """One person, the product rules.

    A failed test does not burn the step down: up to two grades lower. When the same answers
    confirm the grade one step below (cat.lower_offer), the person accepts it and stops. A confident
    pass (the session recommends the next grade) earns one separate test one step higher.
    A confirmed grade is never replaced by a lower one. The result is the last confirmed
    grade, or nothing.
    """
    confirmed: str | None = None
    target = declared
    downs = 0
    climbed = False
    sessions = items = 0
    passed_declared = False
    for _ in range(4):
        session = run_session(theta, spec, target, truth, rng, offsets=offsets)
        sessions += 1
        items += session.n
        if sessions == 1:
            passed_declared = session.passed
        if session.passed:
            confirmed = target
            if session.recommended and not climbed:
                climbed = True
                target = session.recommended
                continue
            break
        if confirmed is not None:
            break
        if session.lower_offer:
            confirmed = session.lower_offer
            break
        if downs >= 2:
            break
        lower = prev_grade(target)
        if lower is None:
            break
        downs += 1
        target = lower
    return confirmed, sessions, items, passed_declared


def _cohen(xs: list[str | None], ys: list[str | None]) -> float:
    labels: list[str | None] = [*GRADE_ORDER, None]
    index = {g: i for i, g in enumerate(labels)}
    k = len(labels)
    n = len(xs)
    if n == 0:
        return 1.0
    obs = [[0] * k for _ in range(k)]
    for a, b in zip(xs, ys, strict=True):
        obs[index[a]][index[b]] += 1
    po = sum(obs[i][i] for i in range(k)) / n
    row = [sum(obs[i]) for i in range(k)]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    pe = sum(row[i] * col[i] for i in range(k)) / (n * n)
    return (po - pe) / (1.0 - pe) if pe < 1 else 1.0


def _path_shares(rows: list[tuple[float, str | None]]) -> tuple[float, float, float, float, float]:
    n = max(1, len(rows))
    exact = within = over = under = bare = 0
    for theta, grade in rows:
        truth_g = true_grade(theta)
        ti = GRADE_ORDER.index(truth_g) if truth_g in GRADE_ORDER else None
        ei = GRADE_ORDER.index(grade) if grade in GRADE_ORDER else None
        if grade is None:
            bare += 1
        if grade == truth_g:
            exact += 1
        if (ti is None and ei is None) or (ti is not None and ei is not None and abs(ti - ei) <= 1):
            within += 1
        if ei is not None and (ti is None or ei > ti):
            over += 1
        if ei is not None and ti is not None and ei < ti:
            under += 1
    return exact / n, within / n, over / n, under / n, bare / n


def _under_grade(theta: float, grade: str | None) -> bool | None:
    """True when the confirmed grade is below the true one. None when there is no true grade."""
    truth_g = true_grade(theta)
    if truth_g not in GRADE_ORDER:
        return None
    if grade not in GRADE_ORDER:
        return False
    return GRADE_ORDER.index(grade) < GRADE_ORDER.index(truth_g)


def _group_under(flags: list[bool]) -> tuple[int, float]:
    if not flags:
        return 0, 0.0
    return len(flags), sum(flags) / len(flags)


def path_detail(rows: list[tuple[float, str, str | None, bool]]) -> dict:
    """Where the first path sits low, and how often the declared-level test is passed.

    rows are (theta, declared, confirmed grade, passed the declared level). The random stream is not touched.
    """
    lower, upper = [], []
    below, equal, above = [], [], []
    edges = [-1 + 0.25 * i for i in range(10)]
    passed = [0] * 9
    counted = [0] * 9
    for theta, declared, grade, declared_passed in rows:
        flag = _under_grade(theta, grade)
        truth_g = true_grade(theta)
        if flag is not None and truth_g in GRADE_ORDER:
            (lower if theta - CUTS[truth_g] < 0.5 else upper).append(flag)
            declared_i = GRADE_ORDER.index(declared)
            truth_i = GRADE_ORDER.index(truth_g)
            (below if declared_i < truth_i else equal if declared_i == truth_i else above).append(flag)
        if declared not in GRADE_ORDER:
            continue
        delta = theta - CUTS[declared]
        for i in range(9):
            right = edges[i + 1]
            if edges[i] <= delta < right or (i == 8 and delta == right):
                counted[i] += 1
                passed[i] += int(declared_passed)
                break
    curve = [(edges[i], counted[i], (passed[i] / counted[i] if counted[i] else 0.0)) for i in range(9)]
    shift = None
    for i in range(8):
        left_n, right_n = counted[i], counted[i + 1]
        if not left_n or not right_n:
            continue
        s0, s1 = passed[i] / left_n, passed[i + 1] / right_n
        if s0 < 0.5 <= s1 and s1 != s0:
            d0, d1 = edges[i], edges[i + 1]
            shift = d0 + (0.5 - s0) * (d1 - d0) / (s1 - s0)
            break
    lower_n, lower_under = _group_under(lower)
    upper_n, upper_under = _group_under(upper)
    below_n, below_under = _group_under(below)
    equal_n, equal_under = _group_under(equal)
    above_n, above_under = _group_under(above)
    return {
        "lower_n": lower_n, "lower_under": lower_under,
        "upper_n": upper_n, "upper_under": upper_under,
        "below_n": below_n, "below_under": below_under,
        "equal_n": equal_n, "equal_under": equal_under,
        "above_n": above_n, "above_under": above_under,
        "pass_curve": curve, "half_shift": shift,
    }


def study_paths(people: list[Person], truth: Truth, rng: random.Random,
                offsets: dict[str, float] | None) -> PathStudy:
    first = [simulate_path(theta, spec, declared, truth, rng, offsets) for theta, spec, declared in people]
    second = [simulate_path(theta, spec, declared, truth, rng, offsets) for theta, spec, declared in people]
    left = [(theta, grade) for (theta, _, _), (grade, _, _, _) in zip(people, first, strict=True)]
    right = [(theta, grade) for (theta, _, _), (grade, _, _, _) in zip(people, second, strict=True)]
    exact, within, over, under, bare = _path_shares(left)
    again = _path_shares(right)
    matrix_sessions = []
    for (theta, _, _), (grade, _, _, _) in zip(people, first, strict=True):
        matrix_sessions.append(Session("", "", theta, grade, grade is not None, None, 0, []))
    detail_rows = [
        (theta, declared, grade, passed)
        for (theta, _, declared), (grade, _, _, passed) in zip(people, first, strict=True)
    ]
    detail = path_detail(detail_rows)
    return PathStudy(
        n=len(people), exact=exact, within_one=within, over=over, under=under, unconfirmed=bare,
        mean_sessions=statistics.mean(sessions for _, sessions, _, _ in first),
        mean_items=statistics.mean(items for _, _, items, _ in first),
        again_exact=again[0], again_within=again[1], again_over=again[2], again_under=again[3],
        again_unconfirmed=again[4],
        again_sessions=statistics.mean(sessions for _, sessions, _, _ in second),
        again_items=statistics.mean(items for _, _, items, _ in second),
        kappa=_cohen([g for g, _, _, _ in first], [g for g, _, _, _ in second]),
        weighted_kappa=_quadratic_kappa([g for g, _, _, _ in first], [g for g, _, _, _ in second]),
        matrix=grade_matrix(matrix_sessions),
        **detail,
    )


MISSPEC = ((0.15, 0.15), (0.30, 0.30), (0.50, 0.50))


def study_misspec(people: list[Person], truth: Truth, offsets: dict[str, float] | None,
                  seed: int) -> list[MisspecRow]:
    """Answers from a 4PL the scorer does not know. Scoring still uses the nominal 3PL."""
    rows = []
    half = people[:max(300, len(people) // 2)]
    for index, (sigma_a, sigma_b) in enumerate(MISSPEC):
        rng = random.Random(seed + 50 + index)
        report, _ = cohort(people, truth, rng, offsets=offsets, misspec=(sigma_a, sigma_b))
        again = retest(half, truth, random.Random(seed + 70 + index), offsets or {}, misspec=(sigma_a, sigma_b))
        rows.append(MisspecRow(sigma_a, sigma_b, report.accuracy_clear, report.false_pass, again.kappa))
    return rows


def fixed_form(spec: str = "backend", people: int = 3000, items: int = 40, seed: int = 7) -> FixedForm:
    """Corrected item-total correlation on one fixed form. Ability is N(0, 1), wider than an adaptive test."""
    slots: list[tuple] = []
    for fam in families_for(spec):
        for level in fam.levels:
            if fam.available(spec, level):
                slots.append((fam, level))
    form = []
    cursor = 0
    while len(form) < items and slots:
        form.append(slots[cursor % len(slots)])
        cursor += 1
    prepared = []
    for fam, level in form:
        draw = random.Random(f"{fam.id}:{level}:{len(prepared)}").random()
        c = TYPED_C if draw < typed_share(fam.id, level) else CHOICE_C
        prepared.append((fam.a, LEVEL_B[level], c))
    rng = random.Random(seed)
    columns = [[] for _ in prepared]
    for _ in range(people):
        theta = rng.gauss(0.0, 1.0)
        for index, (a, b, c) in enumerate(prepared):
            columns[index].append(1.0 if rng.random() < p3(theta, a, b, c) else 0.0)
    rs = []
    for index, column in enumerate(columns):
        rest = [sum(row) - column[person] for person, row in enumerate(zip(*columns, strict=True))]
        rs.append(_pearson(column, rest))
    return FixedForm(items=len(form), people=people, median_r=statistics.median(rs) if rs else 0.0,
                     good_share=sum(r >= 0.20 for r in rs) / max(1, len(rs)))


def stolen_sessions(truth: Truth, offsets: dict[str, float] | None, seed: int,
                    n: int = 80, stolen: int = 20) -> StolenSessions:
    """A junior sits middle after seeing 20 other middle sessions. A repeated instance is answered right."""
    rng = random.Random(seed)
    donors = population(stolen, random.Random(seed + 3))
    weak = []
    for _ in range(n):
        theta = rng.uniform(CUTS["junior"], CUTS["middle"])
        weak.append((theta, rng.choice(SPECS), "middle"))
    honest = stolen_pass = fixed = 0
    for index, (theta, spec, target) in enumerate(weak):
        memory: set[tuple] = set()
        donor_rng = random.Random(seed + 1000 + index)
        for donor_theta, donor_spec, _ in donors:
            run_session(donor_theta, donor_spec, "middle", truth, donor_rng, offsets=offsets, remember=memory)
        attack_rng = random.Random(seed + 5000 + index)
        honest += run_session(theta, spec, target, truth, random.Random(seed + 7000 + index),
                              offsets=offsets).passed
        stolen_pass += run_session(theta, spec, target, truth, attack_rng, offsets=offsets, known=memory).passed
        fixed += run_session(theta, spec, target, truth, random.Random(seed + 9000 + index),
                             offsets=offsets, attack="fixed").passed
    return StolenSessions(n=n, honest=honest / n, stolen=stolen_pass / n, fixed=fixed / n)


def run(n: int = 3000, seed: int = 7, extras: bool = True) -> Report:
    rng = random.Random(seed)
    truth = Truth.draw(rng)
    people = population(n, random.Random(seed + 1))
    retest_people = population(max(300, n // 2), random.Random(seed + 2))
    # Pretest cohort: difficulty offsets are estimated before any monitoring starts.
    _, pretest = cohort(population(n, rng), truth, rng)
    offsets = calibrate(pretest)
    clean, clean_sessions = cohort(people, truth, rng, offsets=offsets)
    with choices_only():
        choices, _ = cohort(people, truth, rng, offsets=offsets)
        retest_choices = retest(retest_people, truth, rng, offsets)
        guesser_choices = _guessers(truth, rng)
    clean_alarms = monitor(clean_sessions)
    # The monitor learns on one leaking cohort; the next cohort is then tested twice on the same people and
    # the same random streams, once as is and once with the flagged keys in quarantine.
    _, leak_sessions = cohort(population(n, rng), truth, rng, leak_share=0.3, offsets=offsets)
    stats = monitor(leak_sessions)
    flagged = {k for k, st in stats.items() if st.alarm or st.cusum_alarm}
    leaked_keys = {k for k in stats if k.split(":")[0] in set(MAIN_FAMILY.values()) and stats[k].n >= 30}
    next_people = population(n, random.Random(seed + 5))
    leak, _ = cohort(next_people, truth, rng, leak_share=0.3, offsets=offsets, stream=seed + 6)
    monitored, _ = cohort(next_people, truth, rng, leak_share=0.3, blocked=flagged, offsets=offsets,
                          stream=seed + 6)
    # Ladder: everyone takes the middle test; the pass rate by true grade shows where the test separates.
    ladder_people = [(theta, spec, "middle") for theta, spec, _ in people]
    _, ladder_sessions = cohort(ladder_people, truth, rng, offsets=offsets, stream=seed + 7)
    ladder: dict[str, list[bool]] = {}
    for session in ladder_sessions:
        ladder.setdefault(true_grade(session.theta) or "below", []).append(session.passed)
    served = [c for s in clean_sessions for *_, c, _ in s.answers]
    side = random.Random(seed + 99)
    rates = _collision_rates(side)
    transfer_people = population(min(80, n), random.Random(seed + 98))
    transfer_pass = _attack_pass(transfer_people, truth, side, offsets, rates, fixed=False)
    fixed_pass = _attack_pass(transfer_people, truth, side, offsets, rates, fixed=True)
    mae_before, mae_after = _discrimination_mae(clean_sessions, truth)
    topic_acc, topic_fp = _topic_floor_effect(clean_sessions)
    rudner_acc, rudner_cons, posterior_acc = rudner(clean_sessions)
    multiclass = multiclass_rudner(clean_sessions)
    ece, reliability = reliability_curve(clean_sessions)
    matrix = grade_matrix(clean_sessions)
    overlap = item_overlap(clean_sessions)
    region_peaks = region_exposure(clean_sessions, seed + 17)
    cusum_leaked = len({k for k, st in stats.items() if st.cusum_alarm} & leaked_keys)
    cusum_false = sum(1 for st in clean_alarms.values() if st.cusum_alarm)
    return Report(
        clean=clean, choices=choices, leak=leak, monitored=monitored,
        false_alarms_clean=sum(1 for st in clean_alarms.values() if st.alarm or st.cusum_alarm),
        keys_clean=sum(1 for st in clean_alarms.values() if st.n >= 30),
        leaked_keys=len(leaked_keys), leaked_flagged=len(flagged & leaked_keys),
        other_flagged=len(flagged - leaked_keys),
        retest=retest(retest_people, truth, rng, offsets), retest_choices=retest_choices,
        discrimination=discrimination(clean_sessions),
        typed_share=sum(c < CHOICE_C for c in served) / len(served),
        guesser_pass=_guessers(truth, rng), guesser_pass_choices=guesser_choices,
        blocked=sorted(flagged),
        transfer_pass=transfer_pass, fixed_pass=fixed_pass,
        cusum_leaked=cusum_leaked, cusum_false_clean=cusum_false,
        mae_a_before=mae_before, mae_a_after=mae_after,
        topic_false_pass=topic_fp, topic_accuracy=topic_acc,
        rudner_accuracy=rudner_acc, rudner_consistency=rudner_cons, posterior_accuracy=posterior_acc,
        multiclass_accuracy=multiclass, ece=ece, reliability=reliability,
        grade_matrix=matrix, overlap=overlap, region_peaks=region_peaks,
        ladder={g: (len(v), statistics.mean(v)) for g, v in ladder.items()},
        spec_rows=spec_exposure(clean_sessions),
        overlap_spec=overlap_within_spec(clean_sessions),
        path=study_paths(people, truth, random.Random(seed + 11), offsets) if extras else None,
        misspec=study_misspec(people, truth, offsets, seed) if extras else [],
        fixed_form=fixed_form(seed=seed) if extras else None,
        stolen=stolen_sessions(truth, offsets, seed + 31) if extras else None,
        adjacent_auc=adjacent_auc(clean_sessions, draws=1000 if extras else 200),
    )


# The clean scenario must hold these in CI (`--check`); the seed is fixed, so a failure is a regression.
CHECKS = {
    "accuracy_clear ≥ 0.85": lambda r: r.clean.accuracy_clear >= 0.85,
    "false_pass ≤ 0.12": lambda r: r.clean.false_pass <= 0.12,
    "false_recommend ≤ 0.03": lambda r: r.clean.false_recommend <= 0.03,
    "retest kappa ≥ 0.35": lambda r: r.retest.kappa >= 0.35,
    "guesser_pass ≤ 0.02": lambda r: r.guesser_pass <= 0.02,
    # Guessing flattens an item with options, so its floor is lower.
    "typed median r ≥ 0.20": lambda r: r.discrimination["typed"].median_r >= 0.20,
    "choice median r ≥ 0.15": lambda r: r.discrimination["choice"].median_r >= 0.15,
    # A key from another draw of the same family must not pass the test.
    "transfer_pass ≤ 0.02": lambda r: r.transfer_pass <= 0.02,
    # Quarantine must not make leaked keys pay off more: same people, same streams, with and without it.
    "quarantine false_pass ≤ no monitoring": lambda r: r.monitored.false_pass <= r.leak.false_pass,
    "path overgrade ≤ 0.05": lambda r: r.path is not None and r.path.over <= 0.05,
}

# The nine bars that already guarded the clean scenario. The stopping-rule grid may not add the path bar.
CORE_CHECKS = {name: fn for name, fn in list(CHECKS.items())[:9]}


def _row(name: str, r: CohortReport) -> str:
    return (f"| {name} | {r.accuracy:.1%} | {r.accuracy_clear:.1%} | {r.sensitivity:.1%} | "
            f"{r.false_pass:.1%} | {r.false_recommend:.1%} | "
            f"{r.mean_len:.1f} / {r.p90_len} | {r.stopped_early:.0%} | {r.max_exposure:.0%} | "
            f"{r.spec_max_exposure:.0%} | {r.concept_share:.0%} |")


def _retest_row(name: str, r: Retest) -> str:
    return (f"| {name} | {r.agreement:.0%} | {r.kappa:.2f} | {r.agreement_clear:.0%} | {r.same_grade:.0%} | "
            f"{r.theta_r:.2f} |")


def _disc_row(name: str, d: Discrimination) -> str:
    return (f"| {name} | {d.keys} | {d.median_r:.2f} | {d.good_share:.0%} | {d.weak_right:.0%} | "
            f"{d.strong_right:.0%} |")


def _region_line(r: Report) -> str:
    peaks = ", ".join(f"{p:.0%}" for p in r.region_peaks)
    high = max(r.region_peaks) if r.region_peaks else 0.0
    ratio = (min(r.region_peaks) / high) if high else 1.0
    return (
        "- Экспозиция по регионам: четыре метки назначены отдельным генератором и в выбор задания не входят. "
        f"Максимальная доля одного ключа в группах: {peaks}. Отношение меньшей к большей: {ratio:.2f}."
    )


def _reliability_lines(r: Report) -> list[str]:
    if not r.reliability:
        return []
    lines = [
        "",
        f"Калибровка вероятности уровня. ECE = {r.ece:.3f}. "
        "В корзине — средняя p_pass и доля тех, у кого θ не ниже порога заявленного грейда.",
        "",
        "| p_pass | Людей | Средняя p_pass | Доля θ ≥ порога |",
        "|---|---|---|---|",
    ]
    for i, (count, mean_p, rate) in enumerate(r.reliability):
        if count == 0:
            lines.append(f"| {i / 10:.1f}–{(i + 1) / 10:.1f} | 0 | — | — |")
        else:
            lines.append(f"| {i / 10:.1f}–{(i + 1) / 10:.1f} | {count} | {mean_p:.1%} | {rate:.1%} |")
    lines.append("")
    return lines


def _spec_lines(r: Report) -> list[str]:
    if not r.spec_rows:
        return []
    lines = [
        "Экспозиция ключа внутри специализации, сценарий «без утечки». Знаменатель — сессии этой специализации, "
        f"не все сразу. Перекрытие внутри специализации {r.overlap_spec:.1%}.",
        "",
        "| Специализация | Людей | Макс. доля ключа | Ключ |",
        "|---|---|---|---|",
    ]
    for spec, share, key, people in r.spec_rows:
        lines.append(f"| {spec} | {people} | {share:.0%} | {key} |")
    lines.append("")
    return lines


def markdown(r: Report, n: int, seed: int) -> str:
    return "\n".join([
        f"Симуляция: {n} кандидатов на сценарий, seed {seed}. Команда: "
        f"`python -m app.validation.assessment --n {n} --seed {seed}`. Сценарии «без утечки» и «все задания "
        f"с вариантами» проходят одни и те же кандидаты; ответ вводится в {r.typed_share:.0%} выданных заданий.",
        "",
        "| Сценарий | Точность «сдал/не сдал» | Точность вне ±0,5 от порога | Сдали из тех, кто на уровне | "
        "Ложно сдали | Ложная рекомендация теста выше | "
        "Заданий: среднее / 90 % | Решено до лимита | Экспозиция по всем | "
        "В специализации (макс. по 11) | Доля концептуальных |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        _row("Без утечки", r.clean),
        _row("Без утечки, все задания с вариантами", r.choices),
        _row("Утечка у 30 %, без мониторинга", r.leak),
        _row("Утечка у 30 %, ключи на карантине", r.monitored),
        "",
        *_spec_lines(r),
        f"Повторный тест: {r.retest.pairs} кандидатов проходят тест дважды, задания каждый раз новые.",
        "",
        "| Формат | Тот же итог «сдал/не сдал» | Каппа Коэна | То же вне ±0,5 от порога | Тот же грейд | "
        "Корреляция оценок θ |",
        "|---|---|---|---|---|---|",
        _retest_row("Числовой ответ вводится", r.retest),
        _retest_row("Все задания с вариантами", r.retest_choices),
        "",
        "Различающая сила заданий в сценарии «без утечки». r — точечно-бисериальная корреляция ответа "
        "с оценкой способности по остальным семействам теста.",
        "",
        "| Формат ответа | Ключей с ≥ 30 ответами | Медиана r | Ключей с r ≥ 0,20 | Верно у тех, кто на 0,5 слабее "
        "задания | Верно у тех, кто на 0,5 сильнее |",
        "|---|---|---|---|---|---|",
        _disc_row("Число вводится", r.discrimination["typed"]),
        _disc_row("Выбор из четырёх", r.discrimination["choice"]),
        "",
        f"- Мониторинг утечки: из {r.leaked_keys} утёкших ключей с ≥ 30 ответами пойманы {r.leaked_flagged}, "
        f"ложных срабатываний среди остальных — {r.other_flagged}; на чистых данных — {r.false_alarms_clean} "
        f"из {r.keys_clean} ключей.",
        f"- Случайное угадывание проходит тест в {r.guesser_pass:.1%} случаев "
        f"(все задания с вариантами — {r.guesser_pass_choices:.1%}).",
        f"- Точный грейд в сценарии «без утечки»: {r.clean.exact_grade:.1%}, в пределах одной ступени: "
        f"{r.clean.within_one:.1%}, завышение: {r.clean.overgrade:.1%}.",
        f"- Взвешенная каппа повторного теста (квадратичные веса по грейду): {r.retest.weighted_kappa:.2f}.",
        f"- Зона неопределённости (NEW-2): решение «на границе», если |θ̂ − порог| < SE по первому тесту. "
        f"Таких {r.retest.borderline_share:.1%}. У уверенных решений повтор даёт тот же итог в "
        f"{r.retest.agreement_confident:.1%} (95 % ДИ бутстрепа {r.retest.agreement_confident_ci[0]:.1%}–"
        f"{r.retest.agreement_confident_ci[1]:.1%}), у пограничных — в {r.retest.agreement_borderline:.1%}.",
        f"- Ключ от другого экземпляра того же семейства: сдают {r.transfer_pass:.1%}. "
        f"Ключ от того же экземпляра (фиксированный банк): сдают {r.fixed_pass:.1%}.",
        f"- Второй сигнал утечки (CUSUM): поймано {r.cusum_leaked} утёкших ключей, "
        f"ложных тревог на чистых данных — {r.cusum_false_clean}. "
        f"Карантин ставится, если сработал z или CUSUM.",
        f"- Калибровка различимости, средняя ошибка a: до {r.mae_a_before:.3f}, после {r.mae_a_after:.3f}."
        + (" Банк заданий её не принимает: ошибка на симуляции не снижается."
           if r.mae_a_after > r.mae_a_before else ""),
        f"- Если слабая тема блокирует сдачу: точность {r.topic_accuracy:.1%}, ложные сдачи {r.topic_false_pass:.1%} "
        f"(в продукте порог по теме не включён, пока сравнение не подтвердит его).",
        f"- Точность классификации по Руднеру у порога заявленного грейда: {r.rudner_accuracy:.1%}, "
        f"согласованность без учёта порога 0,75: {r.rudner_consistency:.1%}. "
        f"С учётом порога предсказано {r.retest.decision_consistency:.1%}, "
        f"на повторе измерено {r.retest.agreement:.1%}. "
        f"Многоклассовая точность по Руднеру: {r.multiclass_accuracy:.1%}. "
        f"Вероятность принятого решения по апостериорному распределению: {r.posterior_accuracy:.1%}.",
        *_reliability_lines(r),
        f"- Перекрытие заданий: в среднем другой кандидат этой же симуляции видел {r.overlap:.1%} "
        f"заданий данного кандидата. Максимальная экспозиция ключа — в таблице выше.",
        f"- Два теста одного кандидата: во втором в среднем {r.retest.own_overlap:.1%} заданий совпадают "
        f"с первым по семейству и уровню. Сами задания собираются заново, а ключ от другого экземпляра "
        f"того же семейства сдаёт {r.transfer_pass:.1%}.",
        f"- Карантин на тех же людях и тех же случайных потоках: ложные сдачи {r.leak.false_pass:.1%} без "
        f"мониторинга и {r.monitored.false_pass:.1%} с карантином.",
        _region_line(r),
        "",
        "Матрица «истинный грейд по θ × грейд, который назначила сессия» в сценарии «без утечки». "
        "Строка «ниже» — способность ниже стажёра или сессия не назначила грейд.",
        "",
        "| Истинный \\ назначенный | " + " | ".join(MATRIX_LABELS) + " |",
        "|" + "---|" * (len(MATRIX_LABELS) + 1),
        *[
            f"| {MATRIX_LABELS[i]} | " + " | ".join(str(cell) for cell in row) + " |"
            for i, row in enumerate(r.grade_matrix)
        ],
        "",
        "Лестница: все кандидаты проходят тест на middle. Доля сдавших по истинному грейду.",
        "",
        "| Истинный грейд | Кандидатов | Сдали тест middle |",
        "|---|---|---|",
        *[f"| {MATRIX_LABELS[i]} | {r.ladder[g][0]} | {r.ladder[g][1]:.1%} |"
          for i, g in enumerate(("below", *GRADE_ORDER)) if g in r.ladder],
        "",
        *_auc_lines(r),
        *_path_lines(r),
        *_misspec_lines(r),
        *_form_lines(r),
        *_stolen_lines(r),
    ])


def _path_lines(r: Report) -> list[str]:
    path = r.path
    if path is None:
        return []
    def _row(name: str, exact: float, within: float, over: float, under: float, bare: float,
             sessions: float, items: float) -> str:
        return (f"| {name} | {exact:.1%} | {within:.1%} | {over:.1%} | {under:.1%} | {bare:.1%} | "
                f"{sessions:.2f} | {items:.1f} |")

    return [
        "После пути. Заявленный грейд, затем правила продукта: не сдал — до двух шагов вниз, попытка не сгорает; "
        "сдал и сессия рекомендует ступень выше — один отдельный тест на неё. Итог — последний подтверждённый "
        "грейд или «не подтверждён». Точный грейд считает «нет грейда» совпадением, если способность ниже стажёра. "
        "±1 включает точные. Завышение — подтверждённый грейд выше истинного.",
        "",
        "| Путь | Точный грейд | ±1 | Завышение | Занижение | Не подтверждён | Сессий | Заданий |",
        "|---|---|---|---|---|---|---|---|",
        _row("Первый", path.exact, path.within_one, path.over, path.under, path.unconfirmed,
             path.mean_sessions, path.mean_items),
        _row("Повторный", path.again_exact, path.again_within, path.again_over, path.again_under,
             path.again_unconfirmed, path.again_sessions, path.again_items),
        "",
        *_path_detail_lines(path),
        f"Согласованность двух путей: каппа Коэна итогового грейда {path.kappa:.2f}, "
        f"взвешенная каппа {path.weighted_kappa:.2f}.",
        "",
        "Матрица «истинный грейд по θ × итоговый грейд после пути».",
        "",
        "| Истинный \\ итоговый | " + " | ".join(MATRIX_LABELS) + " |",
        "|" + "---|" * (len(MATRIX_LABELS) + 1),
        *[f"| {MATRIX_LABELS[i]} | " + " | ".join(str(cell) for cell in row) + " |"
          for i, row in enumerate(path.matrix)],
        "",
    ]


def _path_detail_lines(path: PathStudy) -> list[str]:
    """Three cuts of the same first path: where in the true grade, what was declared, and the pass curve."""
    def share(n: int, rate: float) -> str:
        return "—" if n == 0 else f"{rate:.1%}"

    lines = [
        "Те же люди, первый путь. Занижение — подтверждённый грейд ниже истинного; без грейда в эту долю не входит.",
        "",
        "Положение в истинном грейде. Нижняя половина: θ − порог истинного грейда < 0,5.",
        "",
        "| Половина | Людей | Занижено |",
        "|---|---|---|",
        f"| Нижняя | {path.lower_n} | {share(path.lower_n, path.lower_under)} |",
        f"| Верхняя | {path.upper_n} | {share(path.upper_n, path.upper_under)} |",
        "",
        "Заявленный грейд относительно истинного.",
        "",
        "| Заявил | Людей | Занижено |",
        "|---|---|---|",
        f"| Ниже истинного | {path.below_n} | {share(path.below_n, path.below_under)} |",
        f"| Тот же | {path.equal_n} | {share(path.equal_n, path.equal_under)} |",
        f"| Выше истинного | {path.above_n} | {share(path.above_n, path.above_under)} |",
        "",
        "Доля сдавших тест заявленного уровня по θ − порог этого грейда. Шаг 0,25, от −1 до 1,25.",
        "",
        "| θ − порог | Людей | Сдали |",
        "|---|---|---|",
    ]
    for left, n, rate in path.pass_curve:
        lines.append(f"| {left:+.2f} | {n} | {share(n, rate)} |")
    if path.half_shift is None:
        lines.append("")
        lines.append("Доля 0,5 между соседними корзинами не пересекается.")
    else:
        lines.append("")
        lines.append(
            f"θ − порог, где доля сдавших равна 0,5: {path.half_shift:+.3f} "
            "(линейная интерполяция между соседними корзинами)."
        )
    lines.append("")
    return lines


def _auc_lines(r: Report) -> list[str]:
    if not r.adjacent_auc:
        return []
    lines = [
        "Разделение соседних грейдов. AUC — вероятность, что у кандидата старшего грейда оценка θ̂ выше, "
        "чем у кандидата младшего (Mann–Whitney, Hanley & McNeil 1982). 95 % интервал — перцентильный бутстрап, "
        "1000 повторов, выборка внутри каждого грейда отдельно. Истинный грейд — по θ из симуляции.",
        "",
        "| Пара грейдов | Людей (младший / старший) | AUC | 95 % ДИ |",
        "|---|---|---|---|",
    ]
    for row in r.adjacent_auc:
        lines.append(f"| {row.lower} / {row.upper} | {row.n_lower} / {row.n_upper} | {row.auc:.3f} | "
                     f"{row.ci[0]:.3f}–{row.ci[1]:.3f} |")
    lines.append("")
    return lines


def _misspec_lines(r: Report) -> list[str]:
    if not r.misspec:
        return []
    lines = [
        "Ошибка модели. Ответ рисуется четырёхпараметрической кривой, которую оценщик не знает: "
        "a умножается на exp(N(0, σ_a)), b сдвигается на N(0, σ_b), c растёт на U(0, 0,1), верхняя асимптота 0,95. "
        "Оценщик по-прежнему считает номинальной трёхпараметрической моделью.",
        "",
        "| σ_a | σ_b | Точность вне ±0,5 от порога | Ложно сдали | Каппа повтора |",
        "|---|---|---|---|---|",
    ]
    for row in r.misspec:
        lines.append(f"| {row.sigma_a:.2f} | {row.sigma_b:.2f} | {row.accuracy_clear:.1%} | "
                     f"{row.false_pass:.1%} | {row.kappa:.2f} |")
    lines.append("")
    return lines


def _form_lines(r: Report) -> list[str]:
    form = r.fixed_form
    if form is None:
        return []
    adaptive = r.discrimination["typed"].median_r
    return [
        f"Фиксированная форма: {form.items} заданий всех уровней специализации backend, {form.people} человек, "
        f"θ ~ N(0, 1). Скорректированная корреляция задания с суммой остальных: медиана {form.median_r:.2f}, "
        f"доля r ≥ 0,2 — {form.good_share:.0%}. В адаптивном тесте медиана r для вводимого ответа — {adaptive:.2f}: "
        "у задания видят узкий диапазон способностей, поэтому r ниже.",
        "",
    ]


def _stolen_lines(r: Report) -> list[str]:
    stolen = r.stolen
    if stolen is None:
        return []
    return [
        f"Атака «20 сессий»: {stolen.n} человек с истинным грейдом на ступень ниже middle сдают тест на middle. "
        f"Честная сдача {stolen.honest:.1%}, после 20 чужих сессий на middle {stolen.stolen:.1%} "
        f"(верный ответ только если совпали семейство, уровень и параметры экземпляра), "
        f"фиксированный банк {stolen.fixed:.1%}.",
        "",
    ]


def _apply_stop(max_items: int, alpha: float, beta: float, delta: float) -> None:
    global MAX_ITEMS
    cat_module.MAX_ITEMS = max_items
    cat_module.GLR_ALPHA = alpha
    cat_module.GLR_BETA = beta
    cat_module.GLR_DELTA = delta
    MAX_ITEMS = max_items


def stopping_grid(n: int, seed: int) -> None:
    """Print the stopping-rule grid. Product constants stay as they were when this returns."""
    saved = (cat_module.MAX_ITEMS, cat_module.GLR_ALPHA, cat_module.GLR_BETA, cat_module.GLR_DELTA)
    print(f"Перебор остановки: {n} кандидатов, seed {seed}. "
          "Принять клетку можно только при каппе ≥ 0,52, средней длине ≤ 16,5 и всех 9 проверках.")
    print("| MAX_ITEMS | α = β | δ | Каппа | Точность вне ±0,5 | Ложно сдали | Средняя длина | 9 проверок | Принять |")
    print("|---|---|---|---|---|---|---|---|---|")
    accepted = False
    try:
        for max_items in (20, 24):
            for alpha in (0.10, 0.05):
                for delta in (0.25, 0.35):
                    _apply_stop(max_items, alpha, alpha, delta)
                    try:
                        report = run(n, seed, extras=False)
                    except LookupError as exc:
                        print(f"| {max_items} | {alpha:.2f} | {delta:.2f} | — | — | — | — | нет | нет |")
                        print(f"  не посчитано: {exc}")
                        continue
                    nine = all(fn(report) for fn in CORE_CHECKS.values())
                    accept = report.retest.kappa >= 0.52 and report.clean.mean_len <= 16.5 and nine
                    accepted = accepted or accept
                    print(f"| {max_items} | {alpha:.2f} | {delta:.2f} | {report.retest.kappa:.2f} | "
                          f"{report.clean.accuracy_clear:.1%} | {report.clean.false_pass:.1%} | "
                          f"{report.clean.mean_len:.1f} | {'да' if nine else 'нет'} | "
                          f"{'да' if accept else 'нет'} |")
    finally:
        _apply_stop(*saved)
    if accepted:
        print("Есть клетка, которая проходит порог. Настройки в коде всё равно не переписаны этой командой.")
    else:
        print("Ни одна клетка не прошла порог. Настройки продукта не менялись.")


def sh_step(k: float, shown: float, r_max: float = 0.40) -> float:
    """One Sympson–Hetter update. A key that was not shown keeps its constant."""
    if shown <= 0:
        return k
    return min(1.0, k * r_max / shown)


def _spec_peak(sessions: list[Session]) -> float:
    grouped: dict[str, list[Session]] = {}
    for session in sessions:
        grouped.setdefault(session.spec, []).append(session)
    peak = 0.0
    for group in grouped.values():
        counts = collections.Counter(key for session in group for key in set(session.keys))
        if counts:
            peak = max(peak, max(counts.values()) / len(group))
    return peak


def _binary_kappa(left: list[bool], right: list[bool]) -> float:
    n = len(left)
    if n == 0:
        return 1.0
    po = sum(a == b for a, b in zip(left, right, strict=True)) / n
    p1 = sum(left) / n
    p2 = sum(right) / n
    pe = p1 * p2 + (1.0 - p1) * (1.0 - p2)
    return (po - pe) / (1.0 - pe) if pe < 1.0 else 1.0


def _controlled(people: list[Person], truth: Truth, stream: int,
                by_spec: bool, control: dict[str, float] | None):
    return cohort(people, truth, random.Random(0), stream=stream, by_spec=by_spec, control=control)


def calibrate_sh(n: int, rounds: int = 10, r_max: float = 0.40) -> dict[str, float]:
    """Ten passes on the tuning seeds. K starts at 1 and is never fit on 7 or 2026–2028."""
    control = {item_key(fam, level): 1.0 for fam in FAMILIES.values() for level in fam.levels}
    for round_i in range(rounds):
        shown: dict[str, collections.Counter[str]] = {}
        spec_n: dict[str, int] = {}
        for seed in (101, 102, 103, 104, 105):
            people = population(n, random.Random(seed))
            truth = Truth.draw(random.Random(seed + 50))
            _, sessions = _controlled(people, truth, seed + 80, True, control)
            for session in sessions:
                spec_n[session.spec] = spec_n.get(session.spec, 0) + 1
                shown.setdefault(session.spec, collections.Counter()).update(set(session.keys))
        worst: dict[str, float] = {}
        for spec, counts in shown.items():
            n_here = spec_n[spec]
            for key, count in counts.items():
                worst[key] = max(worst.get(key, 0.0), count / n_here)
        for key, rate in worst.items():
            control[key] = sh_step(control[key], rate, r_max)
        low = sum(value < 0.999 for value in control.values())
        print(f"итерация {round_i + 1}: ключей с K < 1 — {low}", flush=True)
    return control


def sh_holdout(n: int) -> bool:
    """Spec denominator plus calibrated K. Fails closed: a miss is not merged."""
    print(f"Настройка 101–105, проверка 201–205, n={n}, r_max=0.40. Публичные зёрна не используются.")
    control = calibrate_sh(n)
    print("| Зерно | max в спец. было | стало | Δ точности вне ±0,5, п.п. | Δ каппы |")
    print("|---|---|---|---|---|")
    ok = True
    for seed in (201, 202, 203, 204, 205):
        people = population(n, random.Random(seed))
        truth = Truth.draw(random.Random(seed + 50))
        base, base_s = _controlled(people, truth, seed + 11, False, None)
        new, new_s = _controlled(people, truth, seed + 11, True, control)
        _, base_b = _controlled(people, truth, seed + 12, False, None)
        _, new_b = _controlled(people, truth, seed + 12, True, control)
        d_acc = (new.accuracy_clear - base.accuracy_clear) * 100
        d_kappa = _binary_kappa([s.passed for s in new_s], [s.passed for s in new_b]) - _binary_kappa(
            [s.passed for s in base_s], [s.passed for s in base_b])
        peak_base, peak_new = _spec_peak(base_s), _spec_peak(new_s)
        print(f"| {seed} | {peak_base:.3f} | {peak_new:.3f} | {d_acc:+.2f} | {d_kappa:+.3f} |", flush=True)
        if peak_new > 0.55 or d_acc < -1.0 or d_kappa < -0.02:
            ok = False
    print("Порог пройден." if ok else "Порог не пройден. Знаменатель продукта и K не менялись.")
    return ok


def _family_pair(n: int, seed: int) -> tuple[CohortReport, CohortReport]:
    """Clean cohort and the published leak cohort (the next people, stream seed+6)."""
    rng = random.Random(seed)
    truth = Truth.draw(rng)
    people = population(n, random.Random(seed + 1))
    _, pretest = cohort(population(n, rng), truth, rng)
    offsets = calibrate(pretest)
    clean, _ = cohort(people, truth, rng, offsets=offsets)
    leaked_people = population(n, random.Random(seed + 5))
    leak, _ = cohort(leaked_people, truth, rng, leak_share=0.3, offsets=offsets, stream=seed + 6)
    return clean, leak


def family_grid(n: int, seed: int) -> None:
    """Six cells: at most 3, 4 or 5 items from one family, with and without the family knife.

    The product constants are restored when this returns. A cell is accepted only when every
    bar below holds; this command does not write the winner into cat.py.
    """
    saved = (cat_module.MAX_PER_FAMILY, cat_module.FAMILY_KNIFE)
    print(f"Перебор семей: {n} кандидатов, seed {seed}. "
          "Принять клетку можно только если ложные сдачи при утечке ≤ 12 %, без утечки ≤ 8 %, "
          "сдали из тех, кто на уровне ≥ 71 %, точность вдали от порога ≥ 91 % и средняя длина ≤ 15.")
    print("| Потолок семьи | Нож | Ложные сдачи, утечка | Ложные сдачи, чисто | "
          "Сдали на уровне | Точность вдали | Средняя длина | Принять |")
    print("|---|---|---|---|---|---|---|---|")
    accepted = False
    try:
        for cap in (3, 4, 5):
            for knife in (False, True):
                cat_module.MAX_PER_FAMILY = cap
                cat_module.FAMILY_KNIFE = knife
                try:
                    clean, leak = _family_pair(n, seed)
                except LookupError as exc:
                    print(f"| {cap} | {'да' if knife else 'нет'} | — | — | — | — | — | нет |")
                    print(f"  не посчитано: {exc}")
                    continue
                ok = (leak.false_pass <= 0.12 and clean.false_pass <= 0.08
                      and clean.sensitivity >= 0.71 and clean.accuracy_clear >= 0.91
                      and clean.mean_len <= 15.0)
                accepted = accepted or ok
                print(f"| {cap} | {'да' if knife else 'нет'} | {leak.false_pass:.1%} | {clean.false_pass:.1%} | "
                      f"{clean.sensitivity:.1%} | {clean.accuracy_clear:.1%} | {clean.mean_len:.1f} | "
                      f"{'да' if ok else 'нет'} |")
    finally:
        cat_module.MAX_PER_FAMILY, cat_module.FAMILY_KNIFE = saved
    if accepted:
        print("Есть клетка, которая проходит эти пороги. Полный --check и запись в продукт — отдельным шагом.")
    else:
        print("Ни одна клетка не прошла порог. Настройки продукта не менялись.")


def _print_extend(n: int, seed: int) -> None:
    """Full report with the one-time extension on. Product flag is restored afterwards."""
    saved = cat_module.ALLOW_EXTEND
    cat_module.ALLOW_EXTEND = True
    print(f"Продление: ещё {cat_module.EXTEND_ITEMS} заданий, если после {cat_module.MAX_ITEMS} "
          f"вероятность уровня от {cat_module.EXTEND_LOW:.2f} включительно и ниже {cat_module.PASS_P:.2f}. "
          f"{n} кандидатов, seed {seed}.")
    try:
        report = run(n, seed)
    finally:
        cat_module.ALLOW_EXTEND = saved
    print(markdown(report, n, seed))
    print(f"приёмка: сдали на уровне {report.clean.sensitivity:.1%} (порог 77 %), "
          f"ложные сдачи {report.clean.false_pass:.1%} (порог 8,5 %), "
          f"занижение после пути {report.path.under:.1%} (порог 26 %), "
          f"средняя длина {report.clean.mean_len:.1f} (порог 15,5), "
          f"каппа повтора {report.retest.kappa:.2f} (порог 0,47)")
    failed = [name for name, ok in CHECKS.items() if not ok(report)]
    print("checks:", "failed " + ", ".join(failed) if failed else f"all {len(CHECKS)} passed")
    bars = (report.clean.sensitivity >= 0.77 and report.clean.false_pass <= 0.085
            and report.path.under <= 0.26 and report.clean.mean_len <= 15.5
            and report.retest.kappa >= 0.47 and not failed)
    print("принять:", "да" if bars else "нет")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--md", type=str, default=None, help="write the markdown table to this file")
    parser.add_argument("--check", action="store_true", help="fail when the clean scenario breaks CHECKS")
    parser.add_argument("--grid", action="store_true",
                        help="stopping-rule grid; does not change product constants")
    parser.add_argument("--sh-holdout", action="store_true",
                        help="Sympson–Hetter by specialization on 201–205; does not change the product")
    parser.add_argument("--family-grid", action="store_true",
                        help="family cap and knife grid; does not change product constants")
    parser.add_argument("--extend", action="store_true",
                        help="measure one optional extension of 6 items; does not change the product")
    args = parser.parse_args()
    if args.sh_holdout:
        passed = sh_holdout(args.n if args.n != 3000 else 800)
        sys.exit(0 if passed else 1)
    if args.grid:
        stopping_grid(args.n, args.seed)
        return
    if args.family_grid:
        family_grid(args.n, args.seed)
        return
    if args.extend:
        _print_extend(args.n, args.seed)
        return
    report = run(args.n, args.seed)
    text = markdown(report, args.n, args.seed)
    print(text)
    print("quarantined:", ", ".join(report.blocked) or "—")
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(text)
    if args.check:
        failed = [name for name, ok in CHECKS.items() if not ok(report)]
        print("checks:", "failed " + ", ".join(failed) if failed else f"all {len(CHECKS)} passed")
        if failed:
            sys.exit(1)


if __name__ == "__main__":
    main()
