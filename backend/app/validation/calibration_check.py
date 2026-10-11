"""Isotonic recalibration of the level probability on a held-out seed.

    python -m app.validation.calibration_check [--n 2000] [--fit-seed 7] [--test-seed 8]

p_pass of the clean cohort is fitted to the outcome «θ ≥ cut of the target» by pool-adjacent-violators on
one seed and checked on another (Zadrozny & Elkan 2002, doi:10.1145/775047.775151; Guo et al. 2017,
arXiv:1706.04599). ECE uses ten equal bins. The product keeps the raw p_pass: this is a measurement.
"""
from __future__ import annotations

import argparse
import bisect

from app.validation._clean import clean_sessions
from app.validation.assessment import CUTS, Session


def pairs(sessions: list[Session]) -> tuple[list[float], list[float]]:
    return [s.p_pass for s in sessions], [float(s.theta >= CUTS[s.target]) for s in sessions]


def ece(ps: list[float], ys: list[float], bins: int = 10) -> float:
    total = 0.0
    for b in range(bins):
        cell = [(p, y) for p, y in zip(ps, ys, strict=True) if min(int(p * bins), bins - 1) == b]
        if cell:
            gap = sum(p for p, _ in cell) / len(cell) - sum(y for _, y in cell) / len(cell)
            total += len(cell) / len(ps) * abs(gap)
    return total


def fit_isotonic(ps: list[float], ys: list[float]) -> tuple[list[float], list[float]]:
    """Pool adjacent violators. Returns block right edges and block values, non-decreasing."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    blocks: list[list[float]] = []   # [sum_y, count, max_p]
    for i in order:
        blocks.append([ys[i], 1.0, ps[i]])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            y, c, p = blocks.pop()
            blocks[-1][0] += y
            blocks[-1][1] += c
            blocks[-1][2] = p
    return [b[2] for b in blocks], [b[0] / b[1] for b in blocks]


def apply(edges: list[float], values: list[float], p: float) -> float:
    return values[min(bisect.bisect_left(edges, p), len(values) - 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--fit-seed", type=int, default=7)
    parser.add_argument("--test-seed", type=int, default=8)
    args = parser.parse_args()
    fp, fy = pairs(clean_sessions(args.n, args.fit_seed))
    tp, ty = pairs(clean_sessions(args.n, args.test_seed))
    edges, values = fit_isotonic(fp, fy)
    after = [apply(edges, values, p) for p in tp]
    print(f"ECE, обучение на зерне {args.fit_seed}: до {ece(fp, fy):.3f}.")
    print(f"ECE на отложенном зерне {args.test_seed}: до {ece(tp, ty):.3f}, после изотонической {ece(after, ty):.3f}.")


if __name__ == "__main__":
    main()
