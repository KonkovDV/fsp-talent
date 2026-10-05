"""Validation of the adaptive test by simulation: `python -m app.validation.assessment [--n 3000] [--md out.md]`.

There is no labelled data in the hackathon (TZ section 2), so this is a parameter-recovery study run through
the production selector and decision code (app.services.cat). Simulated candidates have a known ability
θ ~ N(0.3, 1) and a declared grade: 60 % declare their true grade, 30 % one level higher, 10 % one lower.

The simulated "truth" is deliberately not the model the service assumes: every item key has its own true
difficulty shift N(0, 0.3²) and discrimination ×U(0.8, 1.2) that the service does not know (uncalibrated
bank), and guessing is c = 0.25. So the numbers include model misfit.

Scenarios:
  clean      no leak; also counts false leak alarms on clean data;
  leak       30 % of candidates know the answers of their specialization's main family (a published solver);
  monitored  the leak monitor ran on the "leak" answers, quarantined keys are excluded, a new cohort is tested.
Plus: retest agreement, test length, item exposure, and random guessing.
"""
from __future__ import annotations

import argparse
import collections
import random
import statistics
from dataclasses import dataclass, field

from app.items import LEVEL_B
from app.items.registry import BLUEPRINTS, FAMILIES
from app.models.assessment import GRADE_ORDER
from app.services.cat import CUTS, MAX_ITEMS, Response, State, choose, decide, evaluate, item_key, p3
from app.services.item_monitor import KeyStats, calibrate_offset, leave_family_out

SPECS = tuple(BLUEPRINTS)
MAIN_FAMILY = {"backend": "py_eval", "fullstack": "js_eval", "frontend": "js_eval", "mobile": "js_eval",
               "ml": "ml_metrics", "devops": "net_ipv4", "security": "sec_decode", "embedded": "emb_bits"}


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
    upgraded: bool
    n: int
    keys: list[str]
    # key, family, a, b, c, correct
    answers: list[tuple[str, str, float, float, float, bool]] = field(default_factory=list)
    theta_hat: float = 0.0


def run_session(theta: float, spec: str, target: str, truth: Truth, rng: random.Random,
                leaked_family: str | None = None, blocked: set[str] | None = None,
                guesser: bool = False, offsets: dict[str, float] | None = None) -> Session:
    state = State(spec=spec, target=target)
    keys: list[str] = []
    answers = []
    while True:
        verdict = evaluate(state)
        if verdict.done:
            break
        ch = choose(state, rng, offsets=offsets, blocked=blocked)
        key = item_key(ch.family, ch.level)
        if guesser:
            correct = rng.random() < 0.25
        elif leaked_family and ch.family.id == leaked_family:
            correct = True
        else:
            p_true = p3(theta, ch.a * truth.a_mult[key], LEVEL_B[ch.level] + truth.offsets[key], ch.c)
            correct = rng.random() < p_true
        state.responses.append(Response(ch.a, ch.b, ch.c, correct))
        state.families_used[ch.family.id] += 1
        state.topics_used[ch.family.topic] += 1
        state.concept_used += ch.family.kind == "concept"
        keys.append(key)
        answers.append((key, ch.family.id, ch.a, ch.b, ch.c, correct))
    out = decide(state)
    s = Session(spec, target, theta, out.earned, out.passed, out.upgraded, state.n, keys, answers, out.theta)
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
    false_upgrade: float       # upgraded although θ < cut of the next grade
    mean_len: float
    p90_len: float
    stopped_early: float       # share of sessions decided before MAX_ITEMS
    max_exposure: float        # highest share of sessions that served one item key
    concept_share: float


def cohort(n: int, truth: Truth, rng: random.Random, leak_share: float = 0.0,
           blocked: set[str] | None = None, offsets: dict[str, float] | None = None
           ) -> tuple[CohortReport, list[Session]]:
    sessions = []
    for _ in range(n):
        theta = rng.gauss(0.3, 1.0)
        spec = rng.choice(SPECS)
        target = _declared(theta, rng)
        leaked = MAIN_FAMILY[spec] if rng.random() < leak_share else None
        sessions.append(run_session(theta, spec, target, truth, rng, leaked, blocked, offsets=offsets))
    right = sum(s.passed == (s.theta >= CUTS[s.target]) for s in sessions)
    clear = [s for s in sessions if abs(s.theta - CUTS[s.target]) > 0.5]
    above = [s for s in sessions if s.theta >= CUTS[s.target]]
    below = [s for s in sessions if s.theta < CUTS[s.target]]
    false_up = sum(1 for s in sessions if s.upgraded and s.theta < CUTS[s.earned])
    lengths = sorted(s.n for s in sessions)
    exposure = collections.Counter(k for s in sessions for k in set(s.keys))
    concept = sum(1 for s in sessions for k in s.keys if FAMILIES[k.split(":")[0]].kind == "concept")
    return CohortReport(
        n=n, accuracy=right / n,
        accuracy_clear=sum(s.passed == (s.theta >= CUTS[s.target]) for s in clear) / max(1, len(clear)),
        sensitivity=sum(s.passed for s in above) / max(1, len(above)),
        false_pass=sum(s.passed for s in below) / max(1, len(below)),
        false_upgrade=false_up / n, mean_len=statistics.mean(lengths),
        p90_len=lengths[int(0.9 * (len(lengths) - 1))],
        stopped_early=sum(s.n < MAX_ITEMS for s in sessions) / n,
        max_exposure=max(exposure.values()) / n,
        concept_share=concept / sum(lengths),
    ), sessions


def monitor(sessions: list[Session]) -> dict[str, KeyStats]:
    stats: dict[str, KeyStats] = collections.defaultdict(KeyStats)
    for s in sessions:
        for key, p, correct in leave_family_out(s.answers, CUTS[s.target]):
            stats[key].add(p, correct)
    return stats


def calibrate(sessions: list[Session]) -> dict[str, float]:
    """Per-key difficulty shift from a pretest cohort, with ability estimated without the key's family."""
    from app.services.cat import Response, posterior
    rows: dict[str, list] = collections.defaultdict(list)
    for s in sessions:
        for fam in {r[1] for r in s.answers}:
            others = [Response(a, b, c, ok) for _, f, a, b, c, ok in s.answers if f != fam]
            theta = posterior(others, prior_mean=CUTS[s.target]).theta
            for key, f, a, b, c, ok in s.answers:
                if f == fam:
                    rows[key].append((theta, a, b, c, ok))
    return {k: calibrate_offset(v) for k, v in rows.items() if len(v) >= 30}


@dataclass
class Report:
    clean: CohortReport
    leak: CohortReport
    monitored: CohortReport
    false_alarms_clean: int
    keys_clean: int
    leaked_keys: int
    leaked_flagged: int
    other_flagged: int
    retest_agreement: float
    guesser_pass: float
    blocked: list[str]


def run(n: int = 3000, seed: int = 7) -> Report:
    rng = random.Random(seed)
    truth = Truth.draw(rng)
    # Pretest cohort: difficulty offsets are estimated before any monitoring starts.
    _, pretest = cohort(n, truth, rng)
    offsets = calibrate(pretest)
    clean, clean_sessions = cohort(n, truth, rng, offsets=offsets)
    clean_alarms = monitor(clean_sessions)
    leak, leak_sessions = cohort(n, truth, rng, leak_share=0.3, offsets=offsets)
    stats = monitor(leak_sessions)
    flagged = {k for k, st in stats.items() if st.alarm}
    leaked_keys = {k for k in stats if k.split(":")[0] in set(MAIN_FAMILY.values()) and stats[k].n >= 30}
    monitored, _ = cohort(n, truth, rng, leak_share=0.3, blocked=flagged, offsets=offsets)

    agree = 0
    retest_n = max(300, n // 5)
    for _ in range(retest_n):
        theta = rng.gauss(0.3, 1.0)
        spec, target = rng.choice(SPECS), _declared(theta, rng)
        a = run_session(theta, spec, target, truth, rng, offsets=offsets)
        b = run_session(theta, spec, target, truth, rng, offsets=offsets)
        agree += a.passed == b.passed
    guess = [run_session(0.0, rng.choice(SPECS), rng.choice(GRADE_ORDER), truth, rng, guesser=True)
             for _ in range(300)]
    return Report(
        clean=clean, leak=leak, monitored=monitored,
        false_alarms_clean=sum(1 for st in clean_alarms.values() if st.alarm),
        keys_clean=sum(1 for st in clean_alarms.values() if st.n >= 30),
        leaked_keys=len(leaked_keys), leaked_flagged=len(flagged & leaked_keys),
        other_flagged=len(flagged - leaked_keys),
        retest_agreement=agree / retest_n,
        guesser_pass=sum(s.passed for s in guess) / len(guess),
        blocked=sorted(flagged),
    )


def _row(name: str, r: CohortReport) -> str:
    return (f"| {name} | {r.accuracy:.1%} | {r.accuracy_clear:.1%} | {r.sensitivity:.1%} | "
            f"{r.false_pass:.1%} | {r.false_upgrade:.1%} | "
            f"{r.mean_len:.1f} / {r.p90_len} | {r.stopped_early:.0%} | {r.max_exposure:.0%} | {r.concept_share:.0%} |")


def markdown(r: Report, n: int, seed: int) -> str:
    return "\n".join([
        f"Симуляция: {n} кандидатов на сценарий, seed {seed}. Команда: "
        f"`python -m app.validation.assessment --n {n} --seed {seed}`.",
        "",
        "| Сценарий | Точность «сдал/не сдал» | Точность вне ±0,5 от порога | Сдали из тех, кто на уровне | "
        "Ложно сдали | Ложное повышение | "
        "Заданий: среднее / 90 % | Решено до лимита | Макс. экспозиция ключа | Доля концептуальных |",
        "|---|---|---|---|---|---|---|---|---|---|",
        _row("Без утечки", r.clean),
        _row("Утечка у 30 %, без мониторинга", r.leak),
        _row("Утечка у 30 %, ключи на карантине", r.monitored),
        "",
        f"- Мониторинг утечки: из {r.leaked_keys} утёкших ключей с ≥ 30 ответами пойманы {r.leaked_flagged}, "
        f"ложных срабатываний среди остальных — {r.other_flagged}; на чистых данных — {r.false_alarms_clean} "
        f"из {r.keys_clean} ключей.",
        f"- Повторный тест: одинаковый итог «сдал/не сдал» в {r.retest_agreement:.0%} пар.",
        f"- Случайное угадывание проходит тест в {r.guesser_pass:.1%} случаев.",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--md", type=str, default=None, help="write the markdown table to this file")
    args = parser.parse_args()
    report = run(args.n, args.seed)
    text = markdown(report, args.n, args.seed)
    print(text)
    print("quarantined:", ", ".join(report.blocked) or "—")
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(text)


if __name__ == "__main__":
    main()
