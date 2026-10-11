"""Operating curves of the session integrity signals on the simulator: `python -m app.validation.detector_curves`.

Model as in `app.validation.integrity` (20 items, 3PL, lognormal times): an honest candidate θ ~ N(0, 1); a
candidate with a leak θ ~ U(−1.5, 0) knows the key of a share of items (default 0.5) and answers them right with
probability 0.95 in 0.08 of the time limit. Unlike that report, both groups get the same tab leaves and copies,
so the risk points do not separate the groups by construction.

For each signal the product functions compute the statistic, then a sweep of thresholds gives the share of
leak sessions flagged (catch rate) and the share of honest sessions flagged (false flags). The row marked ★ is
the threshold the product uses. Signals only ask for a human look; none of them moves the grade.

* risk points — `integrity_level` points; flag at points ≥ T (product: moderate, T = 2);
* fast right answers — `note_pace` count of unlikely fast right answers; flag at count ≥ T (product: 2);
* person fit lz* — `person_fit` at the EAP θ̂ of the session; flag at lz* < T (product: −1.645);
* family CUSUM — max over families of `note_family_cusum` statistics; flag at ≥ T (product: 1.6).

This is a model check: real response times are not known yet.
"""
from __future__ import annotations

import argparse
import math
import random
import statistics

from app.services import cat
from app.services.assessment import FAMILY_CUSUM_H, note_family_cusum, note_pace
from app.services.person_fit import LZ_FLAG, person_fit
from app.services.session_marks import integrity_level

N_ITEMS = 20
SIGNALS = {
    # name: (thresholds, product threshold, flagged(stat, T))
    "Баллы риска (уровень «умеренный»+)": ((1, 2, 3, 4), 2, lambda s, t: s >= t),
    "Быстрые маловероятные верные ответы": ((1, 2, 3, 4, 5), 2, lambda s, t: s >= t),
    "Согласованность ответов lz*": ((-1.0, -1.282, -1.645, -2.0, -2.326), LZ_FLAG, lambda s, t: s < t),
    "CUSUM по семействам": ((1.0, 1.3, 1.6, 2.0, 2.5), FAMILY_CUSUM_H, lambda s, t: s >= t),
}


def _poisson(rng: random.Random, lam: float) -> int:
    k, u, prob = 0, rng.random(), math.exp(-lam)
    acc = prob
    while u > acc:
        k += 1
        prob *= lam / k
        acc += prob
    return k


def session(rng: random.Random, leak: bool, leak_share: float) -> dict[str, float]:
    theta = rng.uniform(-1.5, 0.0) if leak else rng.gauss(0, 1)
    tau = rng.gauss(0, 0.3)
    flags: dict = {}
    cusum: dict = {}
    responses = []
    for i in range(N_ITEMS):
        kind = "code" if rng.random() < 0.4 else "concept"
        limit = 180.0 if kind == "code" else 75.0
        a, b, c = rng.uniform(0.8, 2.0), rng.gauss(0, 1), (0.2 if rng.random() < 0.6 else 0.0)
        p_ref = cat.p3(theta + rng.gauss(0, 0.4), a, b, c)
        if leak and rng.random() < leak_share:
            correct = rng.random() < 0.95
            elapsed = math.exp(math.log(0.08 * limit) + rng.gauss(0, 0.4))
        else:
            correct = rng.random() < cat.p3(theta, a, b, c)
            elapsed = math.exp(math.log(0.4 * limit) - tau + rng.gauss(0, 0.5))
        family = f"fam{i % 5}"
        flags = note_pace(flags, family, correct=correct, elapsed=elapsed, kind=kind,
                          expected_p=p_ref, time_limit=limit)
        cusum = note_family_cusum(cusum, family, correct=correct, elapsed=elapsed, kind=kind, expected_p=p_ref)
        responses.append(cat.Response(a, b, c, correct))
    flags["tab_leaves"] = _poisson(rng, 0.3)
    flags["copies"] = 1 if rng.random() < 0.05 else 0
    theta_hat = cat.posterior(responses).theta
    _, lz_star = person_fit(responses, theta_hat)
    cells = (cusum.get("family_pace") or {}).values()
    top = max((max(c["share_cusum"], c["time_cusum"], c["residual_cusum"]) for c in cells), default=0.0)
    return {
        "Баллы риска (уровень «умеренный»+)": integrity_level(flags)["points"],
        "Быстрые маловероятные верные ответы": int(flags.get("fast_correct") or 0),
        "Согласованность ответов lz*": lz_star,
        "CUSUM по семействам": top,
    }


def curves(n: int, seed: int, leak_share: float) -> dict[str, list[tuple[float, float, float]]]:
    """{signal: [(threshold, catch rate on leak sessions, false-flag rate on honest sessions)]}."""
    rng = random.Random(seed)
    honest = [session(rng, False, leak_share) for _ in range(n)]
    leak = [session(rng, True, leak_share) for _ in range(n)]
    out = {}
    for name, (thresholds, _, flagged) in SIGNALS.items():
        out[name] = [(t, sum(flagged(s[name], t) for s in leak) / n, sum(flagged(s[name], t) for s in honest) / n)
                     for t in thresholds]
    return out


def markdown(by_seed: dict[int, dict], held_out: list[int], n: int, leak_share: float) -> str:
    seeds = sorted(by_seed)
    lines = [f"Кривые сигналов честности: {n} честных и {n} сессий с утечкой {leak_share:.0%} ключей на зерно. "
             "Поймано — доля сессий с утечкой, где сигнал сработал; ложно — доля честных. ★ — порог продукта.", ""]
    for name, (thresholds, product, _) in SIGNALS.items():
        head = " | ".join(f"зерно {s}" for s in seeds)
        lines += [f"**{name}**", "", f"| Порог | {head} | среднее {held_out[0]}–{held_out[-1]} |",
                  "|" + "---|" * (len(seeds) + 2)]
        for i, t in enumerate(thresholds):
            mark = " ★" if t == product else ""
            cells = [f"{by_seed[s][name][i][1]:.1%} / {by_seed[s][name][i][2]:.1%}" for s in seeds]
            ho = [by_seed[s][name][i] for s in held_out if s in by_seed]
            mean = (f"{statistics.mean(r[1] for r in ho):.1%} / {statistics.mean(r[2] for r in ho):.1%}"
                    if ho else "—")
            lines.append(f"| {t:g}{mark} | " + " | ".join(cells) + f" | {mean} |")
        lines.append("")
    lines.append("В ячейке: поймано / ложно.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> str:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=2000)
    ap.add_argument("--seeds", default="7,201,202,203,204,205")
    ap.add_argument("--leak-share", type=float, default=0.5)
    args = ap.parse_args(argv)
    seeds = [int(s) for s in args.seeds.split(",")]
    by_seed = {s: curves(args.sessions, s, args.leak_share) for s in seeds}
    text = markdown(by_seed, [s for s in seeds if s >= 201] or seeds, args.sessions, args.leak_share)
    print(text)
    return text


if __name__ == "__main__":
    main()
