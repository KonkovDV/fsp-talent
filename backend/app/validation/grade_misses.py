"""Why a grade lands outside ±1 of the truth: `python -m app.validation.grade_misses [--n 2000] [--seed 7]`.

The test confirms the grade the candidate declared; it does not search for the true grade. A session that
fails its target ends «не подтверждён», and `within_one` of the main report counts that as a miss whenever
the true grade exists. This splits the misses into: (a) declared above the truth and not confirmed — the
intended outcome; (a2) declared at or below the truth and not confirmed — a false negative at the cut;
(b) confirmed, but two or more steps from the truth; and reports ±1 among confirmed grades only.
Six classes, from «ниже стажёра» to lead.
"""
from __future__ import annotations

import argparse
import collections

from app.validation._clean import clean_sessions
from app.validation.assessment import GRADE_ORDER, Session, true_grade


def _idx(grade: str | None) -> int | None:
    return GRADE_ORDER.index(grade) if grade in GRADE_ORDER else None


def split(sessions: list[Session]) -> dict[str, float]:
    count: collections.Counter[str] = collections.Counter()
    confirmed = within = 0
    for s in sessions:
        t, e, d = _idx(true_grade(s.theta)), _idx(s.earned), _idx(s.target)
        if e is not None:
            confirmed += 1
            within += t is not None and abs(t - e) <= 1
        if (t is None and e is None) or (t is not None and e is not None and abs(t - e) <= 1):
            count["ok"] += 1
        elif e is None:
            count["declared_above" if d is not None and t is not None and d > t else "false_negative"] += 1
        else:
            count["far"] += 1
    n = len(sessions)
    out = {k: count[k] / n for k in ("ok", "declared_above", "false_negative", "far")}
    out["confirmed"] = confirmed / n
    out["within_confirmed"] = within / confirmed if confirmed else 0.0
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    r = split(clean_sessions(args.n, args.seed))
    print(f"Без утечки, {args.n} кандидатов, зерно {args.seed}.")
    print(f"±1 по всем сессиям: {r['ok']:.1%}. Вне ±1: заявил выше и не подтверждён {r['declared_above']:.1%}; "
          f"не подтверждён при заявленном не выше настоящего {r['false_negative']:.1%}; "
          f"подтверждён, но дальше ступени {r['far']:.2%}.")
    print(f"Подтверждено {r['confirmed']:.1%} сессий, среди них ±1: {r['within_confirmed']:.1%}.")


if __name__ == "__main__":
    main()
