"""Four-fifths rule and Skew@k on the matching benchmark, by labels that are not score inputs.

    python -m app.validation.fairness [--seeds 10] [--candidates 800] [--needs 80] [--rounds 1000]

For every need of `app.validation.matching` the production order (`rank(..., "full")`) is cut to the
candidates of the need's role, the applicant pool. Selection = place in the top 10 of that pool; scoring =
place in the upper half, which is the DCWP variant for scoring tools (NYC Local Law 144, rules of
06.04.2023: share above the median score). A group's rate is summed over needs and seeds; the impact ratio
is the rate divided by the highest rate (29 CFR 1607.4(D): below 0.8 is evidence of adverse impact).
Groups with n < 5 are printed and not compared. The 95 % interval is a bootstrap over needs.

Labels. Region: four districts drawn by a separate generator; the score never sees it. Code language: one
language drawn from the candidate's real skills; it follows the role, so the pool is cut by role first.
FSP: has FSP history or not. The FSP axis is a score input required by the brief, so a gap there is
expected and is reported on its own row, not as discrimination. Sex and nationality are not collected.
Skew@k (Geyik et al., KDD 2019) is pooled over needs: share of the label among all top-k slots against its
share among all pool places.
"""
from __future__ import annotations

import argparse
import random

from app.services.exposure_fairness import FLOOR, MIN_GROUP, skew_at_k
from app.validation.matching import make_dataset, rank, seed_list

REGIONS = ("ЦФО", "СЗФО", "ПФО", "СФО")
LANGUAGES = ("Python", "JavaScript", "TypeScript", "Java", "Kotlin", "Go", "C++", "C", "C#", "Rust", "Swift", "PHP")
TOP = 10


def labels(dataset: dict) -> dict[str, dict[str, str]]:
    rng = random.Random(dataset["seed"] + 41)
    out: dict[str, dict[str, str]] = {"region": {}, "language": {}, "fsp": {}}
    for c in dataset["candidates"]:
        cid = c["id"]
        out["region"][cid] = rng.choice(REGIONS)
        langs = [s for s in c["truth"]["skills"] if s in LANGUAGES]
        out["language"][cid] = rng.choice(langs) if langs else "без языка"
        out["fsp"][cid] = "есть ФСП" if c["observed"]["fsp_lcb"] is not None else "нет ФСП"
    return out


def need_rows(dataset: dict) -> list[dict]:
    """One row per need: the role pool in product order, with each label."""
    role_of = {c["id"]: c["observed"]["role"] for c in dataset["candidates"]}
    marks = labels(dataset)
    rows = []
    rng = random.Random(dataset["seed"])
    for need in dataset["needs"]:
        order = [cid for cid in rank(dataset, need, "full", rng) if role_of[cid] == need["role"]]
        rows.append({axis: [marks[axis][cid] for cid in order] for axis in marks})
    return rows


def tally(rows: list[dict], axis: str) -> dict[str, list[int]]:
    """group -> [n, selected, upper half]."""
    out: dict[str, list[int]] = {}
    for row in rows:
        values = row[axis]
        half = len(values) // 2
        for place, value in enumerate(values):
            cell = out.setdefault(value, [0, 0, 0])
            cell[0] += 1
            cell[1] += place < TOP
            cell[2] += place < half
    return out


def ratios(cells: dict[str, list[int]], column: int) -> dict[str, float]:
    rates = {g: c[column] / c[0] for g, c in cells.items() if c[0] >= MIN_GROUP}
    best = max(rates.values(), default=0.0)
    return {g: (r / best if best > 0 else 1.0) for g, r in rates.items()}


def skew(rows: list[dict], axis: str, group: str, k: int) -> float | None:
    top = [v for row in rows for v in row[axis][:k]]
    pool = [v for row in rows for v in row[axis]]
    return skew_at_k(top, pool, group, len(top))


def bootstrap(rows: list[dict], axis: str, rounds: int, seed: int = 11) -> dict[str, tuple[float, float, float, float]]:
    """95 % intervals of the selection and scoring impact ratios, resampling needs."""
    rng = random.Random(seed)
    draws: dict[str, tuple[list[float], list[float]]] = {}
    for _ in range(rounds):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        cells = tally(sample, axis)
        sel, sco = ratios(cells, 1), ratios(cells, 2)
        for g in sel:
            pair = draws.setdefault(g, ([], []))
            pair[0].append(sel[g])
            pair[1].append(sco[g])
    out = {}
    for g, (sel, sco) in draws.items():
        sel.sort()
        sco.sort()
        lo, hi = int(0.025 * len(sel)), min(len(sel) - 1, int(0.975 * len(sel)))
        out[g] = (sel[lo], sel[hi], sco[lo], sco[hi])
    return out


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:+.3f}"


NAMES = {"region": "Регион", "language": "Язык кода", "fsp": "Участие в ФСП (ось балла по ТЗ)"}


def report(rows: list[dict], rounds: int) -> tuple[str, dict]:
    lines = ["| Метка | Группа | n | Доля в топ-10 | IR отбора [95 % ДИ] | Доля выше медианы | IR балла [95 % ДИ]"
             " | Skew@10 | Skew@20 |", "|---|---|---|---|---|---|---|---|---|"]
    summary: dict[str, float] = {}
    for axis in ("region", "language", "fsp"):
        cells = tally(rows, axis)
        sel, sco = ratios(cells, 1), ratios(cells, 2)
        ci = bootstrap(rows, axis, rounds)
        for g in sorted(cells, key=lambda x: -cells[x][0]):
            n, k, up = cells[g]
            if g not in sel:
                lines.append(f"| {NAMES[axis]} | {g} | {n} | {k / n:.3f} | n < {MIN_GROUP}, не сравнивается"
                             " | | | | |")
                continue
            s10, s20 = skew(rows, axis, g, 10), skew(rows, axis, g, 20)
            lo1, hi1, lo2, hi2 = ci.get(g, (float("nan"),) * 4)
            lines.append(f"| {NAMES[axis]} | {g} | {n} | {k / n:.3f} | {sel[g]:.3f} [{lo1:.3f}; {hi1:.3f}] | "
                         f"{up / n:.3f} | {sco[g]:.3f} [{lo2:.3f}; {hi2:.3f}] | {_fmt(s10)} | {_fmt(s20)} |")
        summary[f"{axis}_min_sel"] = min(sel.values())
        summary[f"{axis}_min_score"] = min(sco.values())
    return "\n".join(lines), summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="10", help="число зёрен от 2026 или список через запятую")
    parser.add_argument("--candidates", type=int, default=800)
    parser.add_argument("--needs", type=int, default=80)
    parser.add_argument("--rounds", type=int, default=1000)
    args = parser.parse_args()
    seeds = seed_list(args.seeds, 2026)
    rows: list[dict] = []
    for seed in seeds:
        rows.extend(need_rows(make_dataset(args.candidates, args.needs, seed)))
    table, summary = report(rows, args.rounds)
    print(f"Зёрна {seeds[0]}..{seeds[-1]} ({len(seeds)}), кандидатов {args.candidates}, потребностей "
          f"{args.needs} на зерно, всего потребностей {len(rows)}. Пул = кандидаты роли потребности.")
    print(table)
    for axis in ("region", "language", "fsp"):
        sel, sco = summary[f"{axis}_min_sel"], summary[f"{axis}_min_score"]
        verdict = "проходит" if min(sel, sco) + 1e-9 >= FLOOR else "ниже 4/5"
        print(f"{NAMES[axis]}: мин. IR отбора {sel:.3f}, мин. IR балла {sco:.3f}, порог {FLOOR} — {verdict}")


if __name__ == "__main__":
    main()
