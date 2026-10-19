"""Which headline numbers hold only by construction, and what they become when the construction is broken.

Two checks, report only (no product rule reads them):

1. Answer model the scorer does not share. The main report draws answers from the same 3PL family the
   test scores with, so its accuracy and kappa partly hold by construction. Here the answers come from
   other models and the scorer is unchanged: a 4PL with parameter error (sigma 0.30), and a
   multidimensional model (an own ability shift per family, sd 0.6) with 5 % slips and extra guessing.
   The pretest calibration is redone on answers from the same foreign model, as a pilot would do.
2. Key from another instance. The main report counts only code families and makes every non-collision
   answer wrong, so its 0 % is partly by construction. Here collisions are measured on all families
   (40 pairs per level) and the attacker answers on own ability when the copied key does not fit.
   The number is the pass rate over the honest pass rate of the same people.

    python -m app.validation.construction_check --n 2000 --seed 7
"""
from __future__ import annotations

import argparse
import math
import random

from app.items import LEVEL_B
from app.items.registry import FAMILIES
from app.validation.assessment import (
    Truth,
    _p4,
    calibrate,
    p3,
    parity,
    population,
    run_session,
)


def _nominal(truth: Truth):
    def answer(theta, ch, c, key, rng):
        return p3(theta, ch.a * truth.a_mult[key], LEVEL_B[ch.level] + truth.offsets[key], c)
    return answer


def _four_pl(sigma: float):
    def answer(theta, ch, c, key, rng):
        a = ch.a * math.exp(rng.gauss(0.0, sigma))
        b = ch.b + rng.gauss(0.0, sigma)
        return _p4(theta, a, b, min(c + rng.uniform(0.0, 0.1), 0.94), 0.95)
    return answer


def _multidim(truth: Truth, sd: float = 0.6, slip: float = 0.05, extra_guess: float = 0.08):
    def factory(rng: random.Random):
        shift: dict[str, float] = {}

        def answer(theta, ch, c, key, rng_item):
            if ch.family.id not in shift:
                shift[ch.family.id] = rng.gauss(0.0, sd)
            p = p3(theta + shift[ch.family.id], ch.a * truth.a_mult[key], LEVEL_B[ch.level] + truth.offsets[key],
                   min(c + extra_guess, 0.9))
            return p * (1.0 - slip)
        return answer
    return factory


def _sessions(people, truth, rng, responder, offsets=None):
    out = []
    for theta, spec, target in people:
        answer = responder(rng) if getattr(responder, "per_person", False) else responder
        out.append(run_session(theta, spec, target, truth, rng, offsets=offsets, responder=answer))
    return out


def model_rows(n: int, seed: int) -> list[tuple[str, dict]]:
    rng = random.Random(seed)
    truth = Truth.draw(rng)
    people = population(n, random.Random(seed + 1))
    pre_people = population(n, random.Random(seed + 3))
    multi = _multidim(truth)
    multi.per_person = True
    rows = []
    for name, responder in (("3PL, как у оценщика", _nominal(truth)),
                            ("4PL, ошибка параметров σ 0,30", _four_pl(0.30)),
                            ("многомерная: сдвиг по семейству σ 0,6, срывы 5 %, угадывание +0,08", multi)):
        run_rng = random.Random(seed + 11)
        offsets = calibrate(_sessions(pre_people, truth, run_rng, responder))
        sessions = _sessions(people, truth, run_rng, responder, offsets)
        p = parity(sessions)
        rows.append((name, {"accuracy": p.accuracy, "overclaim_rejected": p.overclaim_rejected,
                            "honest_confirmed": p.honest_confirmed, "kappa_ability": p.kappa_ability,
                            "trust_accuracy": p.trust_accuracy}))
    return rows


def collision_rates(rng: random.Random, pairs: int = 40) -> dict[str, float]:
    rates: dict[str, float] = {}
    for fam in FAMILIES.values():
        # Alphabetical specialization, not frozenset order: that order follows
        # PYTHONHASHSEED and the rate would change between processes.
        spec = sorted(fam.specs)[0]
        same = total = 0
        for level in fam.levels:
            if not fam.available(spec, level):
                continue
            for _ in range(pairs):
                try:
                    left = fam.generate(random.Random(rng.randrange(1, 2**30)), level, spec)
                    right = fam.generate(random.Random(rng.randrange(1, 2**30)), level, spec)
                except LookupError:
                    continue
                total += 1
                same += left.options[left.correct] == right.options[right.correct]
        if total:
            rates[fam.id] = same / total
    return rates


def transfer_lift(n: int, seed: int) -> dict:
    rng = random.Random(seed)
    truth = Truth.draw(rng)
    people = population(n, random.Random(seed + 98))
    rates = collision_rates(random.Random(seed + 99))
    honest = attack = 0
    for index, (theta, spec, target) in enumerate(people):
        honest += run_session(theta, spec, target, truth, random.Random(seed * 7919 + index)).passed
        attack += run_session(theta, spec, target, truth, random.Random(seed * 7919 + index),
                              attack="transfer_or_own", collision=rates).passed
    codes = [v for k, v in rates.items() if FAMILIES[k].kind == "code"]
    concepts = [v for k, v in rates.items() if FAMILIES[k].kind != "code"]
    return {"people": n, "honest": honest / n, "attack": attack / n,
            "collision_code": sum(codes) / max(1, len(codes)),
            "collision_concept": sum(concepts) / max(1, len(concepts)),
            "worst": max(rates.items(), key=lambda kv: kv[1])}


def pct(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--transfer-n", type=int, default=400)
    args = ap.parse_args()
    print(f"## Модель ответов не совпадает с моделью оценщика (n = {args.n}, зерно {args.seed})\n")
    print("| Откуда ответы | «Сдал / не сдал» верно | Завышенный грейд не подтверждён | "
          "Честный грейд подтверждён | κw грейда по θ̂ |")
    print("|---|---|---|---|---|")
    for name, r in model_rows(args.n, args.seed):
        print(f"| {name} | {pct(r['accuracy'])} (верить анкете {pct(r['trust_accuracy'])}) | "
              f"{pct(r['overclaim_rejected'])} | {pct(r['honest_confirmed'])} | "
              f"{r['kappa_ability']:.2f}".replace(".", ",") + " |")
    t = transfer_lift(args.transfer_n, args.seed)
    print(f"\n## Ключ от другого экземпляра (n = {t['people']}, зерно {args.seed})\n")
    print(f"- Совпадение ответа у двух свежих экземпляров: код {pct(t['collision_code'])}, "
          f"вопросы на понимание {pct(t['collision_concept'])}; хуже всех {t['worst'][0]} "
          f"{pct(t['worst'][1])}.")
    print(f"- Сдают с чужим ключом (где ключ не подходит, отвечают сами): {pct(t['attack'])}; "
          f"честно те же люди: {pct(t['honest'])}; прирост {pct(t['attack'] - t['honest'])}.")


if __name__ == "__main__":
    main()
