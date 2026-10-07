"""Classification CAT: 3PL IRT, EAP posterior on a grid, item choice at the decision cut, sequential stop.

The test answers one question: is the candidate at or above the declared grade (and, if so, clearly at the
next one, which only earns a recommendation to take the next test)? That is a classification problem, so
items are chosen where they inform the decision best, the Fisher information at the grade cut, not at the
current ability estimate, and the test stops as soon as the posterior probability is decided either way.

    P(correct | θ) = c + (1 − c) · σ(a · (θ − b))        3PL; c = 1/4 with options, 0.02 for a typed number
    posterior(θ) ∝ N(θ; μ0, 1) · Π P^x (1 − P)^(1−x)      on a grid −4..4, step 0.05 (EAP)
    p_pass    = P(θ ≥ cut(target) | answers)
    p_upgrade = P(θ ≥ cut(target + 1) | answers)

Stop: at least MIN_ITEMS and both probabilities outside [DECIDED_LOW, DECIDED_HIGH], or MAX_ITEMS.
Decision: pass when p_pass ≥ PASS_P. A test at grade G confirms only G: when also p_upgrade ≥ RECOMMEND_NEXT_P,
the outcome recommends a separate test at G + 1 and does not assign it (Q&A with ФСП: no automatic jump).
Item choice: information at the active cut × blueprint deficit × exposure penalty, then Sympson–Hetter
inside the best RANDOMESQUE. With no measured exposure the window is uniform. Topic and concept shares
are capped.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field

from app.items import Family
from app.items.hierarchy import parent
from app.items.registry import BLUEPRINTS, CONCEPT_MAX_SHARE, expected_guess, families_for
from app.models.assessment import GRADE_ORDER

# Lower edge of each grade. A band is 1.0 wide. Intern is the step under junior, for an internship.
CUTS = {"intern": -2.5, "junior": -1.5, "middle": -0.5, "senior": 0.5, "lead": 1.5}
GRID = [-4.0 + 0.05 * i for i in range(161)]
MIN_ITEMS = 8
MAX_ITEMS = 20
DECIDED_LOW, DECIDED_HIGH = 0.10, 0.90
# The next-level recommendation is a bonus: once the target is passed we keep testing only while it is plausible.
UPGRADE_GIVE_UP = 0.30
PASS_P = 0.75
RECOMMEND_NEXT_P = 0.90
RANDOMESQUE = 5
MAX_PER_FAMILY = 5
TOPIC_SLACK = 0.15
EXPOSURE_TARGET = 0.40


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def p3(theta: float, a: float, b: float, c: float) -> float:
    return c + (1.0 - c) * _sigmoid(a * (theta - b))


def info3(theta: float, a: float, b: float, c: float) -> float:
    """Fisher information of a 3PL item."""
    p = p3(theta, a, b, c)
    if p <= c or p >= 1.0:
        return 0.0
    return a * a * ((p - c) ** 2) / ((1.0 - c) ** 2) * (1.0 - p) / p


@dataclass(frozen=True)
class Response:
    a: float
    b: float
    c: float
    correct: bool


@dataclass(frozen=True)
class Posterior:
    theta: float          # EAP
    se: float             # posterior SD
    weights: tuple[float, ...]

    def prob_at_least(self, cut: float) -> float:
        return sum(w for t, w in zip(GRID, self.weights, strict=True) if t >= cut - 1e-9)


def loglik(r: Response) -> list[float]:
    out = []
    for t in GRID:
        p = min(max(p3(t, r.a, r.b, r.c), 1e-9), 1 - 1e-9)
        out.append(math.log(p if r.correct else 1.0 - p))
    return out


def posterior(responses: list[Response], prior_mean: float = 0.0, prior_sd: float = 1.0,
              cached: list[float] | None = None) -> Posterior:
    if cached is None:
        cached = [0.0] * len(GRID)
        for r in responses:
            cached = [x + y for x, y in zip(cached, loglik(r), strict=True)]
    logs = [ll - 0.5 * ((t - prior_mean) / prior_sd) ** 2 for t, ll in zip(GRID, cached, strict=True)]
    top = max(logs)
    raw = [math.exp(v - top) for v in logs]
    total = sum(raw)
    w = tuple(v / total for v in raw)
    mean = sum(t * x for t, x in zip(GRID, w, strict=True))
    var = sum((t - mean) ** 2 * x for t, x in zip(GRID, w, strict=True))
    return Posterior(mean, math.sqrt(var), w)


def next_grade(target: str) -> str | None:
    i = GRADE_ORDER.index(target)
    return GRADE_ORDER[i + 1] if i + 1 < len(GRADE_ORDER) else None


def prev_grade(target: str) -> str | None:
    i = GRADE_ORDER.index(target)
    return GRADE_ORDER[i - 1] if i > 0 else None


@dataclass
class State:
    """Everything the selector and the stop rule need; rebuilt from stored items on every request."""
    spec: str
    target: str
    responses: list[Response] = field(default_factory=list)
    families_used: Counter = field(default_factory=Counter)
    topics_used: Counter = field(default_factory=Counter)
    concept_used: int = 0
    keys_used: set = field(default_factory=set)
    # Topic shares formed from a vacancy. None: the specialization blueprint.
    blueprint: dict[str, float] | None = None
    _ll: list[float] = field(default_factory=lambda: [0.0] * len(GRID))
    _ll_n: int = 0

    @property
    def n(self) -> int:
        return len(self.responses)

    def post(self) -> Posterior:
        # Log-likelihood is accumulated incrementally: one grid pass per new answer.
        for r in self.responses[self._ll_n:]:
            self._ll = [x + y for x, y in zip(self._ll, loglik(r), strict=True)]
        self._ll_n = len(self.responses)
        return posterior(self.responses, prior_mean=CUTS[self.target], cached=self._ll)


@dataclass(frozen=True)
class Verdict:
    done: bool
    p_pass: float
    p_upgrade: float | None
    theta: float
    se: float
    stop_reason: str | None


# A jury trial is fifteen items and five minutes. It stops on the count, not on the grade decision.
EXPRESS_ITEMS = 15
EXPRESS_MINUTES = 5
EXPRESS_ITEM_S = 20
# Indifference zone around a grade cut (a band is 1.0 wide). GLR stops when the likelihood
# is clear outside this zone and the posterior is on the same side. α = β = 0.10, so the
# threshold is ln((1−β)/α) = ln 9.
GLR_DELTA = 0.25
GLR_ALPHA = 0.10
GLR_BETA = 0.10


def _glr_bounds() -> tuple[float, float]:
    above = math.log((1.0 - GLR_BETA) / GLR_ALPHA)
    below = math.log(GLR_BETA / (1.0 - GLR_ALPHA))
    return above, below


def _likelihood_at(state: State, theta: float) -> float:
    state.post()
    index = int(round((theta - GRID[0]) / 0.05))
    index = max(0, min(len(GRID) - 1, index))
    return state._ll[index]


def sprt_log_lambda(state: State, cut: float) -> float:
    """Wald SPRT at the edges of the indifference zone: ℓ(cut+δ) − ℓ(cut−δ).

    Positive favors «at or above the cut». Likelihood only, no prior.
    """
    return _likelihood_at(state, cut + GLR_DELTA) - _likelihood_at(state, cut - GLR_DELTA)


def glr_log_lambda(state: State, cut: float) -> float:
    """Thompson GLR: max likelihood above cut+δ minus max likelihood below cut−δ.

    Same sign as the SPRT statistic. The maximum on each side uses the grid likelihood.
    """
    state.post()
    lo, hi = cut - GLR_DELTA, cut + GLR_DELTA
    lower = [ll for t, ll in zip(GRID, state._ll, strict=True) if t <= lo + 1e-9]
    upper = [ll for t, ll in zip(GRID, state._ll, strict=True) if t >= hi - 1e-9]
    if not lower or not upper:
        return 0.0
    return max(upper) - max(lower)


def _open_cut(state: State, p_pass: float, p_up: float | None) -> float:
    """The cut the stop rule is currently about. Same choice as item selection."""
    if p_up is not None and not (DECIDED_LOW < p_pass < DECIDED_HIGH):
        return CUTS[next_grade(state.target)]
    return CUTS[state.target]


def evaluate(state: State, item_limit: int | None = None) -> Verdict:
    post = state.post()
    p_pass = post.prob_at_least(CUTS[state.target])
    up = next_grade(state.target)
    p_up = post.prob_at_least(CUTS[up]) if up else None
    if item_limit is not None:
        # The express trial stops on its own count. It does not take the grade decision.
        done = state.n >= item_limit
        return Verdict(done, p_pass, p_up, post.theta, post.se, "express" if done else None)
    decided_pass = p_pass <= DECIDED_LOW or p_pass >= DECIDED_HIGH
    decided_up = p_up is None or p_pass <= DECIDED_LOW or p_up <= UPGRADE_GIVE_UP or p_up >= DECIDED_HIGH
    cut = _open_cut(state, p_pass, p_up)
    side = p_up if cut != CUTS[state.target] and p_up is not None else p_pass
    glr_stop = False
    if state.n >= MIN_ITEMS:
        glr = glr_log_lambda(state, cut)
        above, below = _glr_bounds()
        glr_stop = (glr >= above and side >= 0.5) or (glr <= below and side <= 0.5)
    if state.n >= MAX_ITEMS:
        return Verdict(True, p_pass, p_up, post.theta, post.se, "max_items")
    if state.n >= MIN_ITEMS and decided_pass and decided_up:
        return Verdict(True, p_pass, p_up, post.theta, post.se, "decided")
    # GLR may finish while the posterior is still inside (0.10, 0.90), but only once the
    # next-grade question is already settled and the ratio agrees with the posterior side.
    if glr_stop and decided_up:
        return Verdict(True, p_pass, p_up, post.theta, post.se, "glr")
    return Verdict(False, p_pass, p_up, post.theta, post.se, None)


def active_cut(state: State, verdict: Verdict) -> float:
    """The cut whose decision is still open; information is maximised there."""
    if DECIDED_LOW < verdict.p_pass < DECIDED_HIGH or verdict.p_upgrade is None:
        return CUTS[state.target]
    return CUTS[next_grade(state.target)]


def item_key(family: Family, level: int) -> str:
    return f"{family.id}:{level}"


@dataclass(frozen=True)
class Choice:
    family: Family
    level: int
    a: float
    b: float
    c: float
    score: float


def choose(state: State, rng: random.Random, offsets: dict[str, float] | None = None,
           exposure: dict[str, float] | None = None, blocked: set[str] | None = None) -> Choice:
    """Pick the next family and level.

    offsets: calibrated difficulty shift per item key; exposure: share of recent sessions that used the key;
    blocked: keys quarantined by the leak monitor.
    """
    offsets, exposure, blocked = offsets or {}, exposure or {}, blocked or set()
    verdict = evaluate(state)
    cut = active_cut(state, verdict)
    blueprint = state.blueprint or BLUEPRINTS[state.spec]
    planned = max(MIN_ITEMS, state.n + 1)
    candidates: list[Choice] = []
    for fam in families_for(state.spec):
        if state.families_used[fam.id] >= MAX_PER_FAMILY:
            continue
        share = blueprint.get(fam.topic, 0.0)
        if share <= 0:
            continue
        if state.topics_used[fam.topic] >= math.ceil((share + TOPIC_SLACK) * MAX_ITEMS):
            continue
        if fam.kind == "concept" and state.concept_used + 1 > CONCEPT_MAX_SHARE * planned + 1e-9:
            continue
        deficit = share * planned - state.topics_used[fam.topic]
        for level in fam.levels:
            key = item_key(fam, level)
            if key in blocked or not fam.available(state.spec, level):
                continue
            a, b = parent(fam, level, offsets.get(key, 0.0))
            c = expected_guess(fam.id, level)
            info = info3(cut, a, b, c)
            rate = exposure.get(key, 0.0)
            penalty = min(1.0, EXPOSURE_TARGET / rate) if rate > EXPOSURE_TARGET else 1.0
            candidates.append(Choice(fam, level, a, b, c, info * (1.0 + max(0.0, deficit)) * penalty))
    if not candidates:
        raise LookupError(f"no eligible items for {state.spec}")
    candidates.sort(key=lambda ch: -ch.score)
    return sympson_hetter(candidates[:RANDOMESQUE], rng, exposure)


def sympson_hetter(window: list[Choice], rng: random.Random, exposure: dict[str, float]) -> Choice:
    """Serve one item from the randomesque window.

    An empty exposure record keeps the uniform draw. Once a key's share is above the target,
    it is served with probability target/rate. The last item in the window is certain, so the
    test never stalls.
    """
    if not window:
        raise LookupError("empty item window")
    if not exposure or len(window) == 1:
        return rng.choice(window)
    for choice in window[:-1]:
        rate = exposure.get(item_key(choice.family, choice.level), 0.0)
        probability = 1.0 if rate <= EXPOSURE_TARGET else EXPOSURE_TARGET / rate
        if rng.random() < probability:
            return choice
    return window[-1]


@dataclass(frozen=True)
class Outcome:
    earned: str | None        # the target when passed; target-1 is informational only; None: undecided or lower
    passed: bool
    recommend_next: str | None  # next grade to take a separate test at (P(θ ≥ its cut) ≥ RECOMMEND_NEXT_P)
    p_pass: float
    p_upgrade: float | None
    theta: float
    se: float


def decide(state: State) -> Outcome:
    post = state.post()
    target = state.target
    p_pass = post.prob_at_least(CUTS[target])
    up = next_grade(target)
    p_up = post.prob_at_least(CUTS[up]) if up else None
    if p_pass >= PASS_P:
        recommend = up if up and p_up is not None and p_up >= RECOMMEND_NEXT_P else None
        return Outcome(target, True, recommend, p_pass, p_up, post.theta, post.se)
    lower = prev_grade(target)
    if lower and post.prob_at_least(CUTS[lower]) >= PASS_P:
        return Outcome(lower, False, None, p_pass, p_up, post.theta, post.se)
    return Outcome(None, False, None, p_pass, p_up, post.theta, post.se)


# A claimed grade is not confirmed when any topic with enough items was mostly wrong.
TOPIC_FLOOR_N = 2
TOPIC_FLOOR = 0.50


def topic_fails(topics: dict[str, tuple[int, int]]) -> bool:
    """True when a topic with at least TOPIC_FLOOR_N items is below TOPIC_FLOOR right."""
    return any(n >= TOPIC_FLOOR_N and right < TOPIC_FLOOR * n for n, right in topics.values())


def skill_scores(rows: list[tuple[tuple[str, ...], bool]], min_items: int = 3) -> dict[str, float]:
    """Share of right answers per skill tag, for skills with at least `min_items` items."""
    seen: Counter = Counter()
    right: Counter = Counter()
    for skills, correct in rows:
        for s in skills:
            seen[s] += 1
            right[s] += int(correct)
    return {s: right[s] / seen[s] for s in seen if seen[s] >= min_items}
