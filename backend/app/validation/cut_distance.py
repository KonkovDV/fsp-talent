"""Pass/fail accuracy against the distance of the true ability to the cut:
`python -m app.validation.cut_distance --n 2000 --seed 7`.

The sessions are the clean cohort of the main report (`sim_base.clean_run`). Bins of |θ − cut of the declared
grade|; in each: people, share of right decisions with a percentile bootstrap 95 % interval, false passes among
those below the cut and passes among those at or above it. One curve joins the overall accuracy and the
accuracy more than 0.5 from the cut. Rudner 2005, doi:10.7275/56a5-6b14 (classification accuracy).
"""
from __future__ import annotations

import argparse

from app.services.cat import CUTS
from app.validation.assessment import Session, _bootstrap_ci
from app.validation.sim_base import clean_run, digest

EDGES = (0.0, 0.1, 0.2, 0.3, 0.5, 1.0, float("inf"))


def bins(sessions: list[Session]) -> list[dict]:
    out = []
    for lo, hi in zip(EDGES, EDGES[1:], strict=False):
        rows = [s for s in sessions if lo <= abs(s.theta - CUTS[s.target]) < hi]
        right = [s.passed == (s.theta >= CUTS[s.target]) for s in rows]
        below = [s.passed for s in rows if s.theta < CUTS[s.target]]
        above = [s.passed for s in rows if s.theta >= CUTS[s.target]]
        ci = _bootstrap_ci(right) if right else (None, None)
        out.append({"lo": lo, "hi": hi, "n": len(rows), "accuracy": sum(right) / len(rows) if rows else None,
                    "ci": ci, "false_pass": sum(below) / len(below) if below else None,
                    "pass_above": sum(above) / len(above) if above else None})
    return out


def monotone(rows: list[dict]) -> bool:
    """Accuracy does not fall from one bin to the next (empty bins are skipped)."""
    acc = [r["accuracy"] for r in rows if r["accuracy"] is not None]
    return all(b >= a for a, b in zip(acc, acc[1:], strict=False))


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def report(n: int, seed: int) -> tuple[str, dict]:
    rows = bins(clean_run(n, seed).sessions)
    lines = [f"{n} кандидатов, зерно {seed}, сценарий «без утечки» основного отчёта.", "",
             "| |θ − порог| | Людей | Верное решение (95 % ДИ) | Ложно сдали среди тех, кто ниже | "
             "Сдали среди тех, кто на уровне |", "|---|---|---|---|---|"]
    for r in rows:
        span = f"> {r['lo']:g}" if r["hi"] == float("inf") else f"{r['lo']:g}–{r['hi']:g}"
        ci = "" if r["ci"][0] is None else f" ({_pct(r['ci'][0])}–{_pct(r['ci'][1])})"
        lines.append(f"| {span} | {r['n']} | {_pct(r['accuracy'])}{ci} | {_pct(r['false_pass'])} | "
                     f"{_pct(r['pass_above'])} |")
    lines += ["", f"Точность не убывает с расстоянием: {'да' if monotone(rows) else 'нет'}.",
              f"sha256 {digest(rows)}"]
    return "\n".join(lines), {"rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    print(report(args.n, args.seed)[0])


if __name__ == "__main__":
    main()
