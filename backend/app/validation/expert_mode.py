"""Expert mode for the jury: the production adaptive test on a simulated candidate of a chosen level.

The item selector, the 3PL posterior, the stop rule and the grade decision are the ones the live test uses
(app.services.cat via app.validation.assessment.run_session). Only the answers are simulated: the candidate
has a known ability θ, and every item key has its own true difficulty shift and discrimination that the
service does not know (Truth.draw on a seed of its own, apart from the validation seeds).

Nothing is read from or written to the database. No item text, options or answer keys leave this module:
a step is the family, its topic, the difficulty level and whether the simulated answer was right.
"""
from __future__ import annotations

import random

from app.items.registry import FAMILIES
from app.models.assessment import GRADE_ORDER
from app.services.cat import CUTS, MAX_ITEMS, Response, State, evaluate, posterior
from app.validation.assessment import SPECS, Truth, run_session, true_grade

# A truth of its own: not one of the tuning, holdout or published validation seeds.
EXPERT_TRUTH_SEED = 6_060_606
MAX_BATCH = 50
THETA_MIN, THETA_MAX = -3.5, 3.5
STOP_RU = {
    "decided": "решение принято: вероятность по обе стороны порога определилась",
    "glr": "решение принято по отношению правдоподобий у порога",
    "max_items": "достигнут предел заданий",
}

_truth: Truth | None = None


def _bank_truth() -> Truth:
    global _truth
    if _truth is None:
        _truth = Truth.draw(random.Random(EXPERT_TRUTH_SEED))
    return _truth


def level_theta(grade: str) -> float:
    """The middle of the grade's band on the θ scale (a band is 1.0 wide)."""
    return CUTS[grade] + 0.5


def _steps(answers: list[tuple], target: str) -> list[dict]:
    rows, responses = [], []
    for n, (_key, family_id, a, b, c, correct) in enumerate(answers, start=1):
        responses.append(Response(a, b, c, correct, family_id))
        post = posterior(responses, prior_mean=CUTS[target])
        family = FAMILIES[family_id]
        rows.append({
            "n": n,
            "family": family.title,
            "topic": family.topic,
            "level": int(_key.split(":")[1]),
            "difficulty": round(b, 2),
            "correct": bool(correct),
            "theta": round(post.theta, 2),
            "se": round(post.se, 2),
            "p_pass": round(post.prob_at_least(CUTS[target]), 3),
        })
    return rows


def _stop_reason(answers: list[tuple], spec: str, target: str) -> str | None:
    state = State(spec=spec, target=target)
    state.responses = [Response(a, b, c, ok, fam) for _k, fam, a, b, c, ok in answers]
    return evaluate(state).stop_reason


def simulate(*, spec: str = "backend", grade: str | None = "middle", theta: float | None = None,
             target: str | None = None, seed: int | None = None, batch: int = 0) -> dict:
    """One full session step by step, plus `batch` repeats on fresh items with the share of matching grades."""
    if spec not in SPECS:
        raise ValueError("spec")
    if theta is None:
        if grade not in GRADE_ORDER:
            raise ValueError("grade")
        theta = level_theta(grade)
    if not THETA_MIN <= theta <= THETA_MAX:
        raise ValueError("theta")
    truth_grade = true_grade(theta)
    target = target or truth_grade or GRADE_ORDER[0]
    if target not in GRADE_ORDER:
        raise ValueError("target")
    if not 0 <= batch <= MAX_BATCH:
        raise ValueError("batch")
    if seed is None:
        seed = random.SystemRandom().randrange(1, 2**31)
    truth = _bank_truth()
    session = run_session(theta, spec, target, truth, random.Random(seed))
    out = {
        "spec": spec,
        "theta": round(theta, 2),
        "true_grade": truth_grade,
        "target": target,
        "cut": CUTS[target],
        "seed": seed,
        "steps": _steps(session.answers, target),
        "items": session.n,
        "max_items": MAX_ITEMS,
        "stop_reason": STOP_RU.get(_stop_reason(session.answers, spec, target) or "", None),
        "theta_hat": round(session.theta_hat, 2),
        "se": round(session.se, 2),
        "p_pass": round(session.p_pass, 3),
        "passed": session.passed,
        "earned": session.earned,
    }
    if batch:
        runs = [run_session(theta, spec, target, truth, random.Random(seed * 1_000_003 + i + 1))
                for i in range(batch)]
        lengths = sorted(r.n for r in runs)
        out["batch"] = {
            "n": batch,
            "same_as_first": round(sum(r.earned == session.earned for r in runs) / batch, 3),
            "same_as_truth": round(sum(r.earned == truth_grade for r in runs) / batch, 3),
            "passed": round(sum(r.passed for r in runs) / batch, 3),
            "median_items": lengths[batch // 2],
            "grades": {g or "none": sum(r.earned == g for r in runs) for g in (*GRADE_ORDER, None)
                       if any(r.earned == g for r in runs)},
        }
    return out
