"""Empirical coverage of θ̂ ± z·SE: `python -m app.validation.interval_coverage --n 2000 --seed 7`.

θ̂ is the posterior mean and SE the posterior SD of the live test (prior at the cut of the declared grade).
Share of sessions whose true θ lies inside θ̂ ± z·SE for z = 1, 1.645 and 1.96 (nominal 68.3 / 90 / 95 %),
overall and by true grade, for the full test (clean cohort of the main report) and the express mode on the
same people. Also the SD of (θ̂ − θ) / SE: 1 when the stated uncertainty is honest. Cook, Gelman & Rubin 2006,
doi:10.1198/106186006X136976; Bock & Mislevy 1982, doi:10.1177/014662168200600405.
"""
from __future__ import annotations

import argparse
import math
import statistics

from app.models.assessment import GRADE_ORDER
from app.validation.assessment import Session, express_sessions, true_grade
from app.validation.sim_base import clean_run, digest

Z = ((1.0, 0.6827), (1.645, 0.90), (1.96, 0.95))


def coverage(sessions: list[Session]) -> dict:
    n = len(sessions)
    if not n:
        return {"n": 0, "cover": [None] * len(Z), "z_sd": None, "mean_se": None}
    cover = [sum(abs(s.theta_hat - s.theta) <= z * s.se for s in sessions) / n for z, _ in Z]
    zs = [(s.theta_hat - s.theta) / s.se for s in sessions if s.se > 0]
    return {"n": n, "cover": cover, "z_sd": statistics.pstdev(zs) if len(zs) > 1 else None,
            "mean_se": statistics.mean(s.se for s in sessions)}


def by_grade(sessions: list[Session]) -> list[tuple[str, dict]]:
    groups: dict[str, list[Session]] = {}
    for s in sessions:
        groups.setdefault(true_grade(s.theta) or "ниже", []).append(s)
    order = ["ниже", *GRADE_ORDER]
    return [(g, coverage(groups[g])) for g in order if g in groups]


def _pct(x: float | None) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:.1f}%"


def report(n: int, seed: int) -> tuple[str, dict]:
    base = clean_run(n, seed)
    express = express_sessions(base.people, base.truth, base.offsets, seed + 41)
    payload: dict = {}
    head = "| Группа | Людей | ±1·SE (68,3 %) | ±1,645·SE (90 %) | ±1,96·SE (95 %) | SD (θ̂ − θ)/SE | Средняя SE |"
    lines = [f"{n} кандидатов, зерно {seed}. Номинал в заголовках столбцов.", ""]
    for title, sessions in (("Полный тест", base.sessions), ("Экспресс-режим", express)):
        rows = [("все", coverage(sessions)), *by_grade(sessions)]
        payload[title] = rows
        lines += [f"**{title}**", "", head, "|---|---|---|---|---|---|---|"]
        for g, c in rows:
            zsd = "—" if c["z_sd"] is None else f"{c['z_sd']:.2f}"
            lines.append(f"| {g} | {c['n']} | {' | '.join(_pct(x) for x in c['cover'])} | {zsd} | "
                         f"{c['mean_se']:.3f} |")
        lines.append("")
    lines.append(f"sha256 {digest(payload)}")
    return "\n".join(lines), payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    print(report(args.n, args.seed)[0])


if __name__ == "__main__":
    main()
