"""Item exposure by instance, next to exposure by key, against the Duolingo English Test thresholds.

    python -m app.validation.instance_exposure [--n 2000] [--seed 7]

`app.validation.assessment` counts an item key (family:level). One key is many generated items: numbers,
tables and code change from candidate to candidate. Here the clean cohort is run again with item generation
on, and every served item gets a fingerprint: sha256 of family, level, the wording (or static key) and the
code. The answer follows from those fields, so two items with one fingerprint have the same answer.

Reported on the same sessions, by key and by instance: the highest share of sessions that saw one item
(over all and inside each of the eleven specializations) and the mean pairwise overlap inside a
specialization (share of a candidate's items that another candidate of that specialization also saw).
Reference: the DET security framework keeps item exposure at or below 10 % and test overlap at or below
15 % (go.duolingo.com/security_framework, citing Way, 1998). A family whose instance exposure exceeds 10 %
anywhere is flagged `low_variety`.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import random

from app.validation.assessment import (
    Session,
    Truth,
    calibrate,
    cohort,
    population,
    run_session,
)

DET_EXPOSURE = 0.10
DET_OVERLAP = 0.15


def fingerprint(instance: tuple) -> str:
    family, level, wording, code = instance
    raw = "\x1f".join([str(family), str(level), str(wording or ""), str(code or "")])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def run_cohort(n: int, seed: int) -> tuple[list[tuple[Session, set[str]]], dict[str, str]]:
    """The clean cohort of `assessment.run` with generation on. Exposure control as in `cohort`."""
    rng = random.Random(seed)
    truth = Truth.draw(rng)
    people = population(n, random.Random(seed + 1))
    population(max(300, n // 2), random.Random(seed + 2))
    _, pretest = cohort(population(n, rng), truth, rng)
    offsets = calibrate(pretest)
    seen: collections.Counter[str] = collections.Counter()
    out = []
    family_of: dict[str, str] = {}
    for index, (theta, spec, target) in enumerate(people):
        rates = {key: count / index for key, count in seen.items()} if index >= 20 else None
        served: set[tuple] = set()
        session = run_session(theta, spec, target, truth, rng, offsets=offsets, exposure=rates, remember=served)
        seen.update(set(session.keys))
        prints = set()
        for item in served:
            mark = fingerprint(item)
            family_of[mark] = str(item[0])
            prints.add(mark)
        out.append((session, prints))
    return out, family_of


def max_share(groups: list[set[str]]) -> tuple[float, str | None]:
    if not groups:
        return 0.0, None
    counts = collections.Counter(item for group in groups for item in group)
    if not counts:
        return 0.0, None
    item, count = counts.most_common(1)[0]
    return count / len(groups), item


def mean_overlap(groups: list[set[str]]) -> float:
    """Mean over candidates of the share of their items another candidate saw (pairwise average)."""
    n = len(groups)
    if n < 2:
        return 0.0
    freq = collections.Counter(item for group in groups for item in group)
    total = 0.0
    for group in groups:
        if group:
            total += sum(freq[item] - 1 for item in group) / (len(group) * (n - 1))
    return total / n


def analyse(rows: list[tuple[Session, set[str]]]) -> dict:
    keys = [set(s.keys) for s, _ in rows]
    inst = [i for _, i in rows]
    by_spec: dict[str, list[int]] = collections.defaultdict(list)
    for index, (s, _) in enumerate(rows):
        by_spec[s.spec].append(index)
    spec_rows = []
    for spec in sorted(by_spec):
        idx = by_spec[spec]
        k_share, k_item = max_share([keys[i] for i in idx])
        i_share, _ = max_share([inst[i] for i in idx])
        spec_rows.append({"spec": spec, "n": len(idx), "key_max": k_share, "key": k_item, "inst_max": i_share,
                          "key_overlap": mean_overlap([keys[i] for i in idx]),
                          "inst_overlap": mean_overlap([inst[i] for i in idx])})
    k_all, _ = max_share(keys)
    i_all, _ = max_share(inst)
    return {"n": len(rows), "key_max": k_all, "inst_max": i_all, "spec": spec_rows,
            "key_overlap_spec": sum(r["key_overlap"] * r["n"] for r in spec_rows) / len(rows),
            "inst_overlap_spec": sum(r["inst_overlap"] * r["n"] for r in spec_rows) / len(rows),
            "items": sum(len(i) for i in inst) / len(rows)}


def low_variety(rows: list[tuple[Session, set[str]]], served_families: dict[str, str]) -> list[tuple[str, float]]:
    """Families with an instance seen by more than 10 % of a specialization's sessions."""
    flagged: dict[str, float] = {}
    by_spec: dict[str, list[set[str]]] = collections.defaultdict(list)
    for s, inst in rows:
        by_spec[s.spec].append(inst)
    for groups in by_spec.values():
        counts = collections.Counter(item for group in groups for item in group)
        for item, count in counts.items():
            share = count / len(groups)
            if share > DET_EXPOSURE:
                fam = served_families.get(item, "?")
                flagged[fam] = max(flagged.get(fam, 0.0), share)
    return sorted(flagged.items(), key=lambda t: -t[1])


def _pct(v: float) -> str:
    return f"{100 * v:.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rows, family_of = run_cohort(args.n, args.seed)
    result = analyse(rows)
    print(f"Сессий {result['n']}, зерно {args.seed}, заданий на сессию в среднем {result['items']:.1f}.")
    print(f"Порог DET: экспозиция ≤ {DET_EXPOSURE:.0%}, перекрытие ≤ {DET_OVERLAP:.0%}.")
    print("| Уровень | Макс. экспозиция по всем | Макс. в специализации | Перекрытие в специализации |")
    print("|---|---|---|---|")
    spec_k = max(r["key_max"] for r in result["spec"])
    spec_i = max(r["inst_max"] for r in result["spec"])
    print(f"| Ключ (семейство:уровень) | {_pct(result['key_max'])} | {_pct(spec_k)} | "
          f"{_pct(result['key_overlap_spec'])} |")
    print(f"| Экземпляр (sha256) | {_pct(result['inst_max'])} | {_pct(spec_i)} | "
          f"{_pct(result['inst_overlap_spec'])} |")
    print()
    print("| Специализация | Людей | Ключ: макс. | Ключ | Экземпляр: макс. | Перекрытие ключей"
          " | Перекрытие экземпляров |")
    print("|---|---|---|---|---|---|---|")
    for r in result["spec"]:
        print(f"| {r['spec']} | {r['n']} | {_pct(r['key_max'])} | {r['key']} | {_pct(r['inst_max'])} | "
              f"{_pct(r['key_overlap'])} | {_pct(r['inst_overlap'])} |")
    print()
    flagged = low_variety(rows, family_of)
    names = ", ".join(f"{fam} {_pct(share)}" for fam, share in flagged) or "нет"
    print(f"Флаг low_variety (экземпляр > {DET_EXPOSURE:.0%} в специализации): {names}")


if __name__ == "__main__":
    main()
