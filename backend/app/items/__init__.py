"""Parametric item families for the grade test.

TZ section 2 forbids a single fixed question set (it leaks) and an LLM call per candidate. A family is a
template with five difficulty levels: `generate(rng, level, spec)` builds a fresh item whose right answer is
computed by code (by running the snippet, the SQL query or the formula), so two candidates practically never
see the same item and publishing one item gives nothing for the next session. Unit tests re-run every
generated snippet in a separate interpreter (Python, Node.js, SQLite) and compare with the stored answer.

Static "concept" items (definitions, status codes) are allowed but capped at 30 % of a session, because a
finite pool can be memorised. Leaks are watched by app.services.item_monitor.
"""
from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

LEVELS = (1, 2, 3, 4, 5)
# Prior difficulty on the theta scale for each level. Grade cuts are -1.5 / -0.5 / 0.5 / 1.5, so the
# levels sit around them; per-level offsets are re-estimated from real answers (item_stats.b_offset).
LEVEL_B = {1: -2.2, 2: -1.2, 3: -0.2, 4: 0.8, 5: 1.8}


@dataclass(frozen=True)
class Item:
    stem: str
    options: list[str]
    correct: int
    explanation: str
    code: str | None = None
    language: str | None = None
    # How a test can re-check the answer independently: {"runner": "python"|"node"|"sqlite", ...}
    verify: dict | None = None
    # Static items carry their own key so leaks are tracked per item, not per family level.
    static_key: str | None = None


@dataclass(frozen=True)
class Family:
    id: str
    title: str
    topic: str
    kind: str                      # "code" (computed answer) | "concept" (finite pool)
    specs: frozenset[str]
    skills: tuple[str, ...]
    generate: Callable[[random.Random, int, str], Item]
    a: float = 1.4                 # discrimination prior
    levels: tuple[int, ...] = LEVELS
    # Optional: (spec, level) -> whether the family has items there (static pools are uneven).
    supports: Callable[[str, int], bool] | None = None
    # Languages the family can show its code in; generate() then accepts lang=... (see families/langs.py).
    languages: tuple[str, ...] = ("python",)

    def available(self, spec: str, level: int) -> bool:
        return spec in self.specs and level in self.levels and (self.supports is None or self.supports(spec, level))


class OptionError(RuntimeError):
    pass


def options_with(rng: random.Random, correct, distractors, filler: Callable[[], object] | None = None,
                 n: int = 4) -> tuple[list[str], int]:
    """Four distinct options with the right one at a random position."""
    right = str(correct)
    seen = [right]
    for d in distractors:
        s = str(d)
        if s not in seen:
            seen.append(s)
        if len(seen) == n:
            break
    tries = 0
    while len(seen) < n:
        tries += 1
        if filler is None or tries > 200:
            raise OptionError(f"cannot build {n} distinct options for {right!r}")
        s = str(filler())
        if s not in seen:
            seen.append(s)
    wrong = seen[1:]
    rng.shuffle(wrong)
    pos = rng.randrange(n)
    opts = wrong[:pos] + [right] + wrong[pos:]
    return opts, pos


def near_int(rng: random.Random, value: int, spread: int = 5) -> Callable[[], int]:
    return lambda: value + rng.choice([-1, 1]) * rng.randint(1, max(1, spread))
