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
from app.items.registry import FAMILIES, typed_share
from app.models.assessment import GRADE_ORDER
from app.services import cat as cat_module
from app.services.cat import CUTS, MAX_ITEMS, Response, State, choose, decide, evaluate, item_key, p3, posterior
from app.services.item_monitor import KeyStats, calibrate_offset, leave_family_out

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


def run_session(theta: float, spec: str, target: str, truth: Truth, rng: random.Random,
                leaked_family: str | None = None, blocked: set[str] | None = None,
                guesser: bool = False, offsets: dict[str, float] | None = None,
                attack: str | None = None, collision: dict[str, float] | None = None,
                exposure: dict[str, float] | None = None) -> Session:
    state = State(spec=spec, target=target)
    keys: list[str] = []
    answers = []
    while True:
        verdict = evaluate(state)
        if verdict.done:
            break
        ch = choose(state, rng, offsets=offsets, blocked=blocked, exposure=exposure)
        key = item_key(ch.family, ch.level)
        typed = _TYPED and rng.random() < typed_share(ch.family.id, ch.level)
        c = TYPED_C if typed else CHOICE_C
        if attack == "fixed":
            correct = True
        elif attack == "transfer":
            correct = rng.random() < (collision or {}).get(ch.family.id, 0.0)
        elif guesser:
            correct = rng.random() < c
        elif leaked_family and ch.family.id == leaked_family:
            correct = True
        else:
            p_true = p3(theta, ch.a * truth.a_mult[key], LEVEL_B[ch.level] + truth.offsets[key], c)
            correct = rng.random() < p_true
        state.responses.append(Response(ch.a, ch.b, c, correct))
        state.families_used[ch.family.id] += 1
        state.topics_used[ch.family.topic] += 1
        state.concept_used += ch.family.kind == "concept"
        keys.append(key)
        answers.append((key, ch.family.id, ch.a, ch.b, c, correct))
    out = decide(state)
    s = Session(spec, target, theta, out.earned, out.passed, out.recommend_next, state.n, keys, answers,
                out.theta, out.se, out.p_pass)
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
    max_exposure: float        # highest share of sessions that served one item key
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
           stream: int | None = None) -> tuple[CohortReport, list[Session]]:
    """`stream` gives every person an own random stream: two designs then differ only by the design
    (the same people leak, the same answers fall the same way until the item sequences part)."""
    sessions = []
    seen: collections.Counter[str] = collections.Counter()
    for index, (theta, spec, target) in enumerate(people):
        if stream is not None:
            rng = random.Random(stream * 1_000_003 + index)
        leaked = MAIN_FAMILY[spec] if rng.random() < leak_share else None
        # The live bank starts Sympson–Hetter after the same warm-up the selector uses.
        rates = {key: count / index for key, count in seen.items()} if index >= 20 else None
        session = run_session(theta, spec, target, truth, rng, leaked, blocked, offsets=offsets,
                              exposure=rates)
        seen.update(set(session.keys))
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


def retest(people: list[Person], truth: Truth, rng: random.Random, offsets: dict[str, float]) -> Retest:
    pairs = [(theta, target, run_session(theta, spec, target, truth, rng, offsets=offsets),
              run_session(theta, spec, target, truth, rng, offsets=offsets)) for theta, spec, target in people]
    agree = [a.passed == b.passed for _, _, a, b in pairs]
    p1 = statistics.mean(a.passed for _, _, a, _ in pairs)
    p2 = statistics.mean(b.passed for _, _, _, b in pairs)
    po, pe = statistics.mean(agree), p1 * p2 + (1 - p1) * (1 - p2)
    clear = [ok for (theta, target, _, _), ok in zip(pairs, agree, strict=True) if abs(theta - CUTS[target]) > 0.5]
    return Retest(
        pairs=len(pairs), agreement=po, kappa=(po - pe) / (1 - pe) if pe < 1 else 1.0,
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


def _guessers(truth: Truth, rng: random.Random) -> float:
    guess = [run_session(0.0, rng.choice(SPECS), rng.choice(GRADE_ORDER), truth, rng, guesser=True)
             for _ in range(300)]
    return sum(s.passed for s in guess) / len(guess)


def run(n: int = 3000, seed: int = 7) -> Report:
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
        grade_matrix=matrix, overlap=overlap, region_peaks=region_peaks,
        ladder={g: (len(v), statistics.mean(v)) for g, v in ladder.items()},
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
}


def _row(name: str, r: CohortReport) -> str:
    return (f"| {name} | {r.accuracy:.1%} | {r.accuracy_clear:.1%} | {r.sensitivity:.1%} | "
            f"{r.false_pass:.1%} | {r.false_recommend:.1%} | "
            f"{r.mean_len:.1f} / {r.p90_len} | {r.stopped_early:.0%} | {r.max_exposure:.0%} | {r.concept_share:.0%} |")


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


def markdown(r: Report, n: int, seed: int) -> str:
    return "\n".join([
        f"Симуляция: {n} кандидатов на сценарий, seed {seed}. Команда: "
        f"`python -m app.validation.assessment --n {n} --seed {seed}`. Сценарии «без утечки» и «все задания "
        f"с вариантами» проходят одни и те же кандидаты; ответ вводится в {r.typed_share:.0%} выданных заданий.",
        "",
        "| Сценарий | Точность «сдал/не сдал» | Точность вне ±0,5 от порога | Сдали из тех, кто на уровне | "
        "Ложно сдали | Ложная рекомендация теста выше | "
        "Заданий: среднее / 90 % | Решено до лимита | Макс. экспозиция ключа | Доля концептуальных |",
        "|---|---|---|---|---|---|---|---|---|---|",
        _row("Без утечки", r.clean),
        _row("Без утечки, все задания с вариантами", r.choices),
        _row("Утечка у 30 %, без мониторинга", r.leak),
        _row("Утечка у 30 %, ключи на карантине", r.monitored),
        "",
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
        f"согласованность {r.rudner_consistency:.1%}. Вероятность принятого решения по апостериорному "
        f"распределению: {r.posterior_accuracy:.1%}.",
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
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--md", type=str, default=None, help="write the markdown table to this file")
    parser.add_argument("--check", action="store_true", help="fail when the clean scenario breaks CHECKS")
    args = parser.parse_args()
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
