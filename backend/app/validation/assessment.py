"""Validation of the test mechanic by simulation: `python -m app.validation.assessment [--n 4000]`.

There is no labelled data in the hackathon (TZ section 2), so the procedure is a parameter-recovery
study. Simulated candidates have a known ability theta ~ N(0.3, 1) and answer the real question bank
by the 2PL model the service assumes. Every session goes through the production functions
(_irt_map, posterior_se, earned_grade), so the numbers describe the code, not a re-implementation.

What it measures (TZ criterion 2):
  * consistency: two independent sessions of the same person give the same outcome;
  * accuracy: the outcome matches the simulated true grade;
  * false upgrades: a confident-result upgrade the true ability does not support;
  * discrimination: how far apart the right-answer rates of weak and strong candidates are;
  * gaming: the score of answering the same letter everywhere.

Limits: the model is the service's own assumption, so these are upper bounds. Real responses add
guessing, item misfit and leaked items; calibrate a and b on real answers before trusting them.
"""
from __future__ import annotations

import argparse
import collections
import random
import statistics
from dataclasses import dataclass

from app.models.assessment import GRADE_ORDER, SESSION_QUESTION_COUNT
from app.seed.questions import QUESTIONS, balanced
from app.services.assessment import (
    _irt_map,
    _sigmoid,
    earned_grade,
    grade_from_theta,
    passed_target,
    posterior_se,
)


def _band(target: str) -> list[dict]:
    i = GRADE_ORDER.index(target)
    grades = {GRADE_ORDER[j] for j in (i - 1, i, i + 1) if 0 <= j < len(GRADE_ORDER)}
    return [q for q in QUESTIONS if q["target_grade"] in grades]


def _session(theta: float, target: str, rng: random.Random) -> tuple[str | None, float, float, int]:
    items = rng.sample(_band(target), min(SESSION_QUESTION_COUNT, len(_band(target))))
    responses = [(q["difficulty"], 1.0, rng.random() < _sigmoid(theta - q["difficulty"])) for q in items]
    est = _irt_map(responses)
    se = posterior_se(est, responses)
    return earned_grade(est, target, se), est, se, len(items)


@dataclass
class Report:
    n: int
    session_length: dict[str, int]
    median_se: float
    retest_exact: float
    retest_pass_fail: float
    accuracy_pass_fail: float
    false_upgrades: float
    right_rate_low: float
    right_rate_high: float
    constant_answer_best: float


def run(n: int = 4000, seed: int = 11) -> Report:
    rng = random.Random(seed)
    exact = pass_fail = accurate = false_up = 0
    ses: list[float] = []
    right_low: list[float] = []
    right_high: list[float] = []
    for _ in range(n):
        theta = rng.gauss(0.3, 1.0)
        target = grade_from_theta(theta) or "junior"   # the candidate declares their true grade
        g1, _, se, _ = _session(theta, target, rng)
        g2, _, _, _ = _session(theta, target, rng)
        ses.append(se)
        exact += g1 == g2
        pass_fail += passed_target(g1, target) == passed_target(g2, target)
        accurate += passed_target(g1, target)
        if g1 is not None and GRADE_ORDER.index(g1) > GRADE_ORDER.index(target):
            false_up += 1
        # Discrimination of the middle-level bank: right-answer rate of the weakest and strongest quartile.
        items = _band("middle")
        rate = sum(rng.random() < _sigmoid(theta - q["difficulty"]) for q in items) / len(items)
        (right_low if theta < -0.37 else right_high if theta > 0.97 else []).append(rate)
    bank = [balanced(q, i) for i, q in enumerate(QUESTIONS)]
    letters = collections.Counter(q["correct_option"] for q in bank)
    return Report(
        n=n,
        session_length={t: min(SESSION_QUESTION_COUNT, len(_band(t))) for t in GRADE_ORDER},
        median_se=statistics.median(ses),
        retest_exact=exact / n,
        retest_pass_fail=pass_fail / n,
        accuracy_pass_fail=accurate / n,
        false_upgrades=false_up / n,
        right_rate_low=statistics.mean(right_low),
        right_rate_high=statistics.mean(right_high),
        constant_answer_best=max(letters.values()) / len(bank),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    r = run(args.n, args.seed)
    print(f"simulated candidates          {r.n}")
    print(f"questions per session         {r.session_length}  (bank: {len(QUESTIONS)})")
    print(f"median SE(theta)              {r.median_se:.2f}  (one grade band is 1.0 wide)")
    print(f"retest, same exact grade      {r.retest_exact:.0%}")
    print(f"retest, same pass/fail        {r.retest_pass_fail:.0%}")
    print(f"pass rate at the true grade   {r.accuracy_pass_fail:.0%}")
    print(f"false upgrades                {r.false_upgrades:.1%}")
    print(f"right answers, weak / strong  {r.right_rate_low:.0%} / {r.right_rate_high:.0%}  (bottom / top quartile)")
    print(f"constant-letter answer        {r.constant_answer_best:.0%} of the bank")


if __name__ == "__main__":
    main()
