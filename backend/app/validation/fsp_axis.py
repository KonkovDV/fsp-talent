"""Does the FSP axis follow hidden skill, and can online appearances pad it?

`python -m app.validation.fsp_axis --seeds 3`

Two thousand people, skill s ~ N(0, 1). A real contest ranks the person against a field drawn from the
same distribution; team results and old results are noisier. Online appearances are bottom-half finishes
whose number does not depend on skill. Scores come from the production engine
(app.services.scoring.engine.compute_discipline_score), not a copy of it.

Three summaries, each correlated with s (Spearman):
  LCB            the axis the product ranks by;
  mean place     mean share of the field left behind (higher is a better finish);
  count          how many protocol rows the person has.

Acceptance on every seed: ρ(LCB, s) > ρ(mean place, s) > ρ(count, s).
A separate farm of 40 online appearances stays under two wins. The grade is not involved.
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
from datetime import date, timedelta

from app.services.scoring.engine import EventInput, compute_discipline_score, percentile
from app.validation.matching import spearman

REF = date(2026, 10, 1)
FARM_EVENTS = 40
FIRST_SEED = 2026


def _event(i: int, place: int, total: int, team: int, months_ago: int) -> EventInput:
    return {
        "id": f"e{i}",
        "place": place,
        "total_participants": total,
        "competition_status": "other",
        "team_size": team,
        "event_date": REF - timedelta(days=months_ago * 30),
    }


def place_in_field(rng: random.Random, skill: float, noise: float, field: int) -> int:
    mine = skill + rng.gauss(0.0, noise)
    better = sum(1 for _ in range(field - 1) if rng.gauss(0.0, 1.0) > mine)
    return better + 1


def history(rng: random.Random, skill: float) -> list[EventInput]:
    """Real contests follow skill. The online tail does not, and some people add a lot of it."""
    events: list[EventInput] = []
    n_real = min(8, max(0, round(rng.gauss(2.5 + 0.4 * skill, 1.2))))
    for _ in range(n_real):
        field = rng.choice((6, 10, 16, 32, 64, 128))
        team = 1 if rng.random() < 0.75 else 4
        place = place_in_field(rng, skill, 0.55 if team == 1 else 1.4, field)
        events.append(_event(len(events), place, field, team, rng.randrange(0, 36)))
    n_online = rng.randint(15, FARM_EVENTS) if rng.random() < 0.20 else rng.randint(0, 2)
    for _ in range(n_online):
        events.append(_event(len(events), rng.randint(55, 100), 100, 1, rng.randrange(0, 8)))
    return events


def farm(n: int = FARM_EVENTS) -> list[EventInput]:
    """Bottom half of an online field. Status is ignored by the engine; the place is what counts."""
    return [_event(i, 70, 100, 1, 1) for i in range(n)]


def two_wins() -> list[EventInput]:
    return [_event(i, 1, 100, 1, 1) for i in range(2)]


def summarize(events: list[EventInput]) -> tuple[float, float, int]:
    scored = compute_discipline_score(events, REF)
    mean_place = statistics.mean(percentile(e["place"], e["total_participants"]) for e in events)
    return scored["lcb"], mean_place, len(events)


def population(n: int, seed: int) -> tuple[list[float], list[float], list[float], list[float], int]:
    rng = random.Random(seed)
    skills, lcbs, places, counts = [], [], [], []
    drawn = 0
    while drawn < n:
        drawn += 1
        skill = rng.gauss(0.0, 1.0)
        events = history(rng, skill)
        if not events:
            continue
        lcb, mean_place, count = summarize(events)
        skills.append(skill)
        lcbs.append(lcb)
        places.append(mean_place)
        counts.append(count)
    return skills, lcbs, places, counts, n - len(skills)


def correlations(n: int, seed: int) -> dict[str, float]:
    skills, lcbs, places, counts, skipped = population(n, seed)
    rho_lcb = spearman(lcbs, skills)
    rho_place = spearman(places, skills)
    rho_count = spearman(counts, skills)
    if rho_lcb is None or rho_place is None or rho_count is None:
        raise RuntimeError(f"корреляция не посчиталась, зерно {seed}")
    return {"lcb": rho_lcb, "place": rho_place, "count": rho_count, "skipped": float(skipped),
            "used": float(len(skills))}


def holds(row: dict[str, float]) -> bool:
    return row["lcb"] > row["place"] > row["count"]


def farm_is_under_two_wins() -> tuple[float, float, bool]:
    padded = compute_discipline_score(farm(), REF)["lcb"]
    wins = compute_discipline_score(two_wins(), REF)["lcb"]
    return padded, wins, padded < wins


def _print_seed(seed: int, row: dict[str, float]) -> None:
    print(f"Зерно {seed}: в корреляции {int(row['used'])} человек"
          f" (без протокола пропущены {int(row['skipped'])}).")
    print(f"  Спирмен LCB со скрытой силой          {row['lcb']:.3f}")
    print(f"  Спирмен среднего места со скрытой силой {row['place']:.3f}")
    print(f"  Спирмен числа строк со скрытой силой   {row['count']:.3f}")
    print(f"  LCB > среднее место > число строк: {'да' if holds(row) else 'нет'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=FIRST_SEED, help="first seed; the rest follow it")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = []
    for i in range(args.seeds):
        seed = args.seed + i
        row = correlations(args.n, seed)
        rows.append(row)
        _print_seed(seed, row)
    padded, wins, farm_ok = farm_is_under_two_wins()
    print(f"Ферма из {FARM_EVENTS} онлайн-участий в нижней половине: LCB {padded:.2f}")
    print(f"Две победы: LCB {wins:.2f}")
    print(f"Ферма ниже двух побед: {'да' if farm_ok else 'нет'}")
    if args.seeds > 1:
        def _spread(key: str) -> str:
            values = [r[key] for r in rows]
            return f"{statistics.mean(values):.3f} ± {statistics.stdev(values):.3f}"

        print("Среднее ± стандартное отклонение по зёрнам: "
              f"LCB {_spread('lcb')}, место {_spread('place')}, число {_spread('count')}")
    ok = farm_ok and all(holds(row) for row in rows)
    if args.check:
        print("checks:", "passed" if ok else "failed")
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
