"""Adaptive test against non-adaptive forms of the same length:
`python -m app.validation.cat_baselines --n 2000 --seed 7`.

The same people, the same hidden truth and the same calibrated bank as the main report. Designs:

    product      the live test: items chosen at the grade cut, GLR stop, 8–20 items, Sympson–Hetter
    cat_L        the same selector, always L items
    linear_L     one fixed form per specialization: L items spread over the blueprint topics and levels 1–5
    random_L     L item keys drawn at random from the specialization bank for each person

Every design ends with the same decision rule (`cat.decide`, prior at the cut of the declared grade).
Metrics: pass/fail accuracy, accuracy more than 0.5 from the cut, false passes, bias and RMSE of θ̂,
grade from the decision rule (exact, ±1), grade read off θ̂ (exact, quadratic weighted kappa), and the
number of items until the posterior SD reaches 0.5 and 0.4 (on 20-item runs). Paired bootstrap of the
difference product − linear over people. Weiss & Kingsbury 1984, doi:10.1111/j.1745-3984.1984.tb01040.x;
Spray & Reckase 1996, doi:10.3102/10769986021004405.
"""
from __future__ import annotations

import argparse
import collections
import math
import random
import statistics
from dataclasses import dataclass

from app.items import CHOICE_C, LEVEL_B, LEVELS, TYPED_C, Family
from app.items.hierarchy import parent
from app.items.registry import BLUEPRINTS, CONCEPT_MAX_SHARE, families_for, typed_share
from app.models.assessment import GRADE_ORDER
from app.services.cat import CUTS, MAX_PER_FAMILY, Response, State, decide, item_key, p3, posterior
from app.validation.assessment import Person, Session, Truth, _quadratic_kappa, run_session, true_grade
from app.validation.sim_base import Base, clean_run, digest

SE_TARGETS = (0.5, 0.4)
LONG = 20


def _slots(spec: str) -> list[tuple[Family, int]]:
    blueprint = BLUEPRINTS[spec]
    return [(fam, level) for fam in families_for(spec) if blueprint.get(fam.topic, 0.0) > 0
            for level in fam.levels if fam.available(spec, level)]


def linear_form(spec: str, length: int) -> list[tuple[Family, int]]:
    """One fixed form: topics follow the blueprint shares, levels are spread evenly over 1–5.

    Deterministic, the same for everyone in the specialization. The family and concept caps of the live
    test hold here too.
    """
    blueprint = BLUEPRINTS[spec]
    fams = [f for f in families_for(spec) if blueprint.get(f.topic, 0.0) > 0]
    used: collections.Counter[str] = collections.Counter()
    topics: collections.Counter[str] = collections.Counter()
    levels: collections.Counter[int] = collections.Counter()
    concept = 0
    form: list[tuple[Family, int]] = []
    for i in range(length):
        def ok(f: Family) -> bool:
            if used[f.id] >= MAX_PER_FAMILY:
                return False
            return not (f.kind == "concept" and concept + 1 > CONCEPT_MAX_SHARE * length + 1e-9)
        pool = [f for f in fams if ok(f)] or [f for f in fams if used[f.id] < MAX_PER_FAMILY] or fams
        fam = min(pool, key=lambda f: (-(blueprint[f.topic] * (i + 1) - topics[f.topic]), used[f.id], f.id))
        options = [lv for lv in fam.levels if fam.available(spec, lv)] or list(LEVELS)
        level = min(options, key=lambda lv: (levels[lv], abs(lv - 3), lv))
        form.append((fam, level))
        used[fam.id] += 1
        topics[fam.topic] += 1
        levels[level] += 1
        concept += fam.kind == "concept"
    return form


def form_session(person: Person, truth: Truth, offsets: dict[str, float], form: list[tuple[Family, int]],
                 rng: random.Random) -> Session:
    """Answers to a given list of item keys, scored like the live test."""
    theta, spec, target = person
    state = State(spec=spec, target=target)
    keys, answers = [], []
    for fam, level in form:
        key = item_key(fam, level)
        a, b = parent(fam, level, offsets.get(key, 0.0))
        c = TYPED_C if rng.random() < typed_share(fam.id, level) else CHOICE_C
        correct = rng.random() < p3(theta, a * truth.a_mult[key], LEVEL_B[level] + truth.offsets[key], c)
        state.responses.append(Response(a, b, c, correct, fam.id))
        state.families_used[fam.id] += 1
        keys.append(key)
        answers.append((key, fam.id, a, b, c, correct))
    out = decide(state)
    return Session(spec, target, theta, out.earned, out.passed, out.recommend_next, state.n, keys, answers,
                   out.theta, out.se, out.p_pass)


def _stream(seed: int, index: int) -> random.Random:
    return random.Random(seed * 1_000_003 + index)


def design_sessions(base: Base, design: str, length: int) -> list[Session]:
    out = []
    forms: dict[str, list] = {}
    for index, person in enumerate(base.people):
        rng = _stream(base.seed + {"cat": 301, "linear": 302, "random": 303}[design] + 10 * length, index)
        theta, spec, target = person
        if design == "cat":
            out.append(run_session(theta, spec, target, base.truth, rng, offsets=base.offsets, item_limit=length))
        elif design == "linear":
            form = forms.setdefault(spec, linear_form(spec, length))
            out.append(form_session(person, base.truth, base.offsets, form, rng))
        else:
            slots = _slots(spec)
            form = [slots[rng.randrange(len(slots))] for _ in range(length)]
            out.append(form_session(person, base.truth, base.offsets, form, rng))
    return out


def _grade_index(grade: str | None) -> int | None:
    return GRADE_ORDER.index(grade) if grade in GRADE_ORDER else None


def items_to_se(session: Session, target: float) -> int | None:
    """Items until the posterior SD (prior at the declared cut) first falls to `target`. None: not within the run."""
    rows: list[Response] = []
    for _, fam_id, a, b, c, correct in session.answers:
        rows.append(Response(a, b, c, correct, fam_id))
        if posterior(rows, prior_mean=CUTS[session.target]).se <= target:
            return len(rows)
    return None


@dataclass
class Row:
    name: str
    mean_len: float
    accuracy: float
    accuracy_clear: float
    false_pass: float
    bias: float
    rmse: float
    grade_exact: float      # decision-rule grade equals the true grade (None counts)
    grade_within_one: float
    theta_grade_exact: float  # grade read off θ̂
    theta_grade_kappa: float


def summarize(name: str, sessions: list[Session]) -> Row:
    n = len(sessions)
    right = [s.passed == (s.theta >= CUTS[s.target]) for s in sessions]
    clear = [r for s, r in zip(sessions, right, strict=True) if abs(s.theta - CUTS[s.target]) > 0.5]
    below = [s.passed for s in sessions if s.theta < CUTS[s.target]]
    errors = [s.theta_hat - s.theta for s in sessions]
    exact = within = 0
    for s in sessions:
        tg = true_grade(s.theta)
        ti, ei = _grade_index(tg), _grade_index(s.earned)
        exact += s.earned == tg
        within += (ti is None and ei is None) or (ti is not None and ei is not None and abs(ti - ei) <= 1)
    truth_g = [true_grade(s.theta) for s in sessions]
    hat_g = [true_grade(s.theta_hat) for s in sessions]
    return Row(name, statistics.mean(s.n for s in sessions), sum(right) / n, sum(clear) / max(1, len(clear)),
               sum(below) / max(1, len(below)), statistics.mean(errors),
               math.sqrt(statistics.mean(e * e for e in errors)), exact / n, within / n,
               sum(a == b for a, b in zip(truth_g, hat_g, strict=True)) / n, _quadratic_kappa(truth_g, hat_g))


def paired_ci(left: list[Session], right: list[Session], clear_only: bool, seed: int = 2026,
              draws: int = 1000) -> tuple[float, float, float]:
    """Mean difference of correct decisions (left − right) on the same people, percentile bootstrap 95 %."""
    diffs = []
    for a, b in zip(left, right, strict=True):
        if clear_only and abs(a.theta - CUTS[a.target]) <= 0.5:
            continue
        cut = CUTS[a.target]
        diffs.append(int(a.passed == (a.theta >= cut)) - int(b.passed == (b.theta >= cut)))
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return sum(diffs) / n, means[int(0.025 * draws)], means[int(0.975 * draws) - 1]


def se_rows(runs: dict[str, list[Session]]) -> list[tuple[str, list[tuple[float, float | None, float]]]]:
    """Per design on 20-item runs: (target SE, mean items among those who reach it, share reaching it)."""
    out = []
    for design, sessions in runs.items():
        cells = []
        for target in SE_TARGETS:
            hits = [k for k in (items_to_se(s, target) for s in sessions) if k is not None]
            cells.append((target, statistics.mean(hits) if hits else None, len(hits) / len(sessions)))
        out.append((design, cells))
    return out


NAMES = {"product": "Продукт: выбор у порога, остановка GLR", "cat": "Адаптивный, всегда {L} заданий",
         "linear": "Линейная форма, {L} заданий", "random": "Случайный набор, {L} заданий"}


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def report(n: int, seed: int) -> tuple[str, dict]:
    base = clean_run(n, seed)
    product = summarize("product", base.sessions)
    short = round(product.mean_len)
    rows = [(NAMES["product"], product)]
    by_design: dict[tuple[str, int], list[Session]] = {}
    for length in (short, LONG):
        for design in ("cat", "linear", "random"):
            sessions = design_sessions(base, design, length)
            by_design[(design, length)] = sessions
            rows.append((NAMES[design].format(L=length), summarize(design, sessions)))
    lines = [f"{n} кандидатов, зерно {seed}: те же люди, скрытая правда и калибровка, что в основном отчёте.", "",
             "| Способ | Заданий | Точность «сдал/не сдал» | Вне ±0,5 от порога | Ложно сдали | Смещение θ̂ | RMSE θ̂ "
             "| Грейд по правилу: точно / ±1 | Грейд по θ̂: точно | κw грейда по θ̂ |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    payload: dict = {"n": n, "seed": seed, "rows": {}}
    for title, r in rows:
        lines.append(f"| {title} | {r.mean_len:.1f} | {_pct(r.accuracy)} | {_pct(r.accuracy_clear)} | "
                     f"{_pct(r.false_pass)} | {r.bias:+.3f} | {r.rmse:.3f} | {_pct(r.grade_exact)} / "
                     f"{_pct(r.grade_within_one)} | {_pct(r.theta_grade_exact)} | {r.theta_grade_kappa:.3f} |")
        payload["rows"][title] = [round(v, 6) if isinstance(v, float) else v for v in vars(r).values()]
    lines += ["", "Продукт минус линейная форма на тех же людях, доля верных решений, бутстреп 1000 повторов:"]
    for length in (short, LONG):
        for clear in (False, True):
            d, lo, hi = paired_ci(base.sessions, by_design[("linear", length)], clear)
            where = "вне ±0,5 от порога" if clear else "все"
            lines.append(f"- против линейной формы из {length} заданий, {where}: {d * 100:+.1f} п. п. "
                         f"(95 % ДИ {lo * 100:+.1f}…{hi * 100:+.1f})")
            payload[f"diff_linear_{length}_{int(clear)}"] = [round(d, 6), round(lo, 6), round(hi, 6)]
    lines += ["", f"Сколько заданий нужно до SE ≤ 0,5 и ≤ 0,4 (прогоны по {LONG} заданий; среднее среди дошедших, "
              "в скобках доля дошедших):", ""]
    runs = {d: by_design[(d, LONG)] for d in ("cat", "linear", "random")}
    for design, cells in se_rows(runs):
        text = "; ".join(f"SE ≤ {t:.1f}: {'—' if k is None else f'{k:.1f}'} ({_pct(s)})" for t, k, s in cells)
        lines.append(f"- {NAMES[design].format(L=LONG)}: {text}")
        payload[f"se_{design}"] = [[t, None if k is None else round(k, 6), round(s, 6)] for t, k, s in cells]
    lines += ["", f"sha256 {digest(payload)}"]
    return "\n".join(lines), payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    print(report(args.n, args.seed)[0])


if __name__ == "__main__":
    main()
