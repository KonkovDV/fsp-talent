"""Simulated false-alarm rate and power of the integrity risk level: `python -m app.validation.integrity`.

Sessions of 20 items with 3PL parameters (a ~ U(0.8, 2.0), b ~ N(0, 1), c = 0.2 for choice items, 0 for typed),
time limits 180 s (code) and 75 s (concept). Response times follow the lognormal model of van der Linden (2006,
doi:10.3102/10769986031002181): log T = log(0.4 · limit) − τ + ε, τ ~ N(0, 0.3), ε ~ N(0, 0.5). The rule sees θ_ref =
true θ + N(0, 0.4) (estimation error before the item), as in production where θ comes from the previous answers.

* Honest: θ ~ N(0, 1); answers by 3PL; hides the tab Poisson(0.3) times, copies the stem with probability 0.05.
* Leak: θ ~ U(−1.5, 0); knows the key of a leaked share of items (0.5), answers them right with probability 0.95
  in 0.08 · limit (lognormal, σ 0.4); other items as honest.

The production functions decide: `note_pace` (G2 rule) and `integrity_level` (W6). 95 % Wilson intervals.
This is a model check, not a field study: real time distributions are not known yet.
"""
from __future__ import annotations

import argparse
import math
import random

from app.services import cat
from app.services.assessment import note_pace
from app.services.session_marks import integrity_level

N_ITEMS = 20


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)


def session(rng: random.Random, leak: bool, leak_share: float) -> dict:
    theta = rng.uniform(-1.5, 0.0) if leak else rng.gauss(0, 1)
    tau = rng.gauss(0, 0.3)
    flags: dict = {}
    for i in range(N_ITEMS):
        kind = "code" if rng.random() < 0.4 else "concept"
        limit = 180.0 if kind == "code" else 75.0
        a, b, c = rng.uniform(0.8, 2.0), rng.gauss(0, 1), (0.2 if rng.random() < 0.6 else 0.0)
        p_true = cat.p3(theta, a, b, c)
        p_ref = cat.p3(theta + rng.gauss(0, 0.4), a, b, c)
        if leak and rng.random() < leak_share:
            correct = rng.random() < 0.95
            elapsed = math.exp(math.log(0.08 * limit) + rng.gauss(0, 0.4))
        else:
            correct = rng.random() < p_true
            elapsed = math.exp(math.log(0.4 * limit) - tau + rng.gauss(0, 0.5))
        flags = note_pace(flags, f"fam{i % 5}", correct=correct, elapsed=elapsed, kind=kind,
                          expected_p=p_ref, time_limit=limit)
    if not leak:
        k = 0
        lam, u, prob = 0.3, rng.random(), math.exp(-0.3)
        acc = prob
        while u > acc:
            k += 1
            prob *= lam / k
            acc += prob
        flags["tab_leaves"] = k
        if rng.random() < 0.05:
            flags["copies"] = 1
    return flags


def run(n: int, seed: int, leak_share: float) -> dict:
    rng = random.Random(seed)
    out = {}
    for name, leak in (("honest", False), ("leak", True)):
        levels = [integrity_level(session(rng, leak, leak_share))["level"] for _ in range(n)]
        mod = sum(lv in ("moderate", "high") for lv in levels)
        out[name] = {"n": n, "moderate_plus": round(mod / n, 4), "ci95": wilson(mod, n),
                     "share": {lv: round(levels.count(lv) / n, 4) for lv in ("none", "low", "moderate", "high")}}
    return out


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--leak-share", type=float, default=0.5)
    args = ap.parse_args(argv)
    report = run(args.sessions, args.seed, args.leak_share)
    for name, row in report.items():
        lo, hi = row["ci95"]
        print(f"{name:<7} «умеренный+» {row['moderate_plus']:.4f} [{lo:.4f}; {hi:.4f}]  уровни {row['share']}")
    return report


if __name__ == "__main__":
    main()
