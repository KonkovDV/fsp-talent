"""Share of CAT stop reasons on simulated sessions near the grade cut.

    cd backend && python tests/stop_reasons.py --n 400 --seed 1

Prints how often each stop rule ends a session (decided / glr / max_items). Used to check what the
documentation says about the sequential stop.
"""
from __future__ import annotations

import argparse
import random
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # `python tests/stop_reasons.py` from backend/

from app.services import cat  # noqa: E402

SPECS = ("backend", "frontend", "data", "qa")


def run(n: int, seed: int) -> Counter:
    rng = random.Random(seed)
    reasons: Counter = Counter()
    for _ in range(n):
        spec, target = rng.choice(SPECS), rng.choice(("junior", "middle", "senior"))
        theta = cat.CUTS[target] + rng.uniform(-0.6, 0.6)
        state = cat.State(spec=spec, target=target)
        while True:
            verdict = cat.evaluate(state)
            if verdict.done:
                break
            choice = cat.choose(state, rng)
            p = cat.p3(theta, choice.a, choice.b, choice.c)
            state.responses.append(cat.Response(choice.a, choice.b, choice.c, rng.random() < p, choice.family.id))
            state.families_used[choice.family.id] += 1
            state.topics_used[choice.family.topic] += 1
            if choice.family.kind == "concept":
                state.concept_used += 1
        reasons[verdict.stop_reason] += 1
    return reasons


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    reasons = run(args.n, args.seed)
    for name, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"{name}: {count} ({count / args.n:.1%})")


if __name__ == "__main__":
    main()
