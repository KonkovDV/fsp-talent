"""EAP (used in the product) against Warm's WLE on simulated sessions: `python -m app.validation.wle_eap`.

Each simulated candidate θ ~ N(0, 1.2) answers 20 items. Items come from a random pool of 400 (a ~ U(0.8, 2.0),
b ~ N(0, 1.2), c = 0.02 for a typed number or 0.25 for four options, 79 % typed as in the product simulation),
picked by maximum Fisher information at the current EAP. The same answers are scored twice:

* EAP — `cat.posterior` with the N(0, 1) prior on the product grid (the product centres the prior on the cut of
  the declared grade; a neutral prior keeps the two estimators on the same footing);
* WLE — Warm (1989): root of dlogL/dθ + J/(2I) = 0 on [−4, 4]; all-right or all-wrong patterns stay finite.

Reported: bias and RMSE of θ̂ − θ (overall and by θ band), and grade agreement with the true grade by the product
cuts (below intern counts as its own step). This is a check of the estimator, not of the product path.
"""
from __future__ import annotations

import argparse
import math
import random
import statistics

from app.services import cat
from app.services.cat import CUTS
from app.validation.matching import quadratic_weighted_kappa

N_ITEMS = 20
POOL = 400
TYPED_SHARE = 0.79
BANDS = ((-9.0, -1.5), (-1.5, 1.5), (1.5, 9.0))
ORDER = ("intern", "junior", "middle", "senior", "lead")


def _parts(theta: float, a: float, b: float, c: float) -> tuple[float, float, float]:
    s = 1.0 / (1.0 + math.exp(-a * (theta - b)))
    p = c + (1 - c) * s
    d1 = a * (1 - c) * s * (1 - s)
    d2 = a * a * (1 - c) * s * (1 - s) * (1 - 2 * s)
    return min(max(p, 1e-9), 1 - 1e-9), d1, d2


def warm_equation(theta: float, responses: list[cat.Response]) -> float:
    score = info = j = 0.0
    for r in responses:
        p, d1, d2 = _parts(theta, r.a, r.b, r.c)
        pq = p * (1 - p)
        score += (int(r.correct) - p) * d1 / pq
        info += d1 * d1 / pq
        j += d1 * d2 / pq
    return score + (j / (2 * info) if info > 0 else 0.0)


def wle(responses: list[cat.Response], lo: float = -4.0, hi: float = 4.0) -> float:
    """Bisection on the Warm equation; the function falls with θ, so a sign change brackets the root."""
    f_lo, f_hi = warm_equation(lo, responses), warm_equation(hi, responses)
    if f_lo <= 0:
        return lo
    if f_hi >= 0:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        if warm_equation(mid, responses) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def grade_index(theta: float) -> int:
    """0 = below intern, 1 = intern … 5 = lead."""
    return sum(theta >= CUTS[g] for g in ORDER)


def simulate(n: int, seed: int) -> list[tuple[float, float, float]]:
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        pool = [(rng.uniform(0.8, 2.0), rng.gauss(0, 1.2), 0.02 if rng.random() < TYPED_SHARE else 0.25)
                for _ in range(POOL)]
        theta = rng.gauss(0, 1.2)
        responses: list[cat.Response] = []
        used: set[int] = set()
        for _ in range(N_ITEMS):
            est = cat.posterior(responses).theta
            k = max((i for i in range(POOL) if i not in used), key=lambda i: cat.info3(est, *pool[i]))
            used.add(k)
            a, b, c = pool[k]
            responses.append(cat.Response(a, b, c, rng.random() < cat.p3(theta, a, b, c)))
        rows.append((theta, cat.posterior(responses).theta, wle(responses)))
    return rows


def summary(rows: list[tuple[float, float, float]]) -> dict:
    out: dict = {}
    for name, col in (("EAP", 1), ("WLE", 2)):
        err = [r[col] - r[0] for r in rows]
        truth = [grade_index(r[0]) for r in rows]
        est = [grade_index(r[col]) for r in rows]
        bands = {}
        for lo, hi in BANDS:
            e = [r[col] - r[0] for r in rows if lo <= r[0] < hi]
            bands[(lo, hi)] = (statistics.mean(e), math.sqrt(statistics.mean(x * x for x in e)), len(e)) if e else None
        out[name] = {
            "bias": statistics.mean(err),
            "rmse": math.sqrt(statistics.mean(x * x for x in err)),
            "exact": sum(a == b for a, b in zip(truth, est, strict=True)) / len(rows),
            "within": sum(abs(a - b) <= 1 for a, b in zip(truth, est, strict=True)) / len(rows),
            "kappa": quadratic_weighted_kappa(truth, est, cats=6),
            "bands": bands,
        }
    return out


def markdown(by_seed: dict[int, dict], n: int) -> str:
    lines = [f"EAP против WLE: {n} симулированных кандидатов на зерно, 20 заданий, выбор по информации.", "",
             "| Зерно | Оценка | Смещение | RMSE | Точный грейд | ±1 грейд | κw | Смещение θ<−1,5 | Смещение θ≥1,5 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for seed, res in sorted(by_seed.items()):
        for name in ("EAP", "WLE"):
            r = res[name]
            low, high = r["bands"][BANDS[0]], r["bands"][BANDS[2]]
            lines.append(f"| {seed} | {name} | {r['bias']:+.3f} | {r['rmse']:.3f} | {r['exact']:.1%} | "
                         f"{r['within']:.1%} | {r['kappa']:.3f} | {low[0]:+.3f} | {high[0]:+.3f} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> str:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seeds", default="7,201,202,203,204,205")
    args = ap.parse_args(argv)
    by_seed = {int(s): summary(simulate(args.n, int(s))) for s in args.seeds.split(",")}
    text = markdown(by_seed, args.n)
    print(text)
    return text


if __name__ == "__main__":
    main()
