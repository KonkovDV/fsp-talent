"""The clean cohort of `python -m app.validation.assessment`, rebuilt step by step for side reports.

`clean_run(n, seed)` repeats the first steps of `assessment.run`: the same hidden truth, the same people,
the same pretest calibration and the same clean cohort. The side reports therefore describe the sessions
behind the main table (78.5 % and 91.5 % at n = 2000, seed 7) and do not change it.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass

from app.validation.assessment import Person, Session, Truth, calibrate, cohort, population


@dataclass
class Base:
    seed: int
    truth: Truth
    offsets: dict[str, float]
    people: list[Person]
    sessions: list[Session]


def clean_run(n: int = 2000, seed: int = 7) -> Base:
    rng = random.Random(seed)
    truth = Truth.draw(rng)
    people = population(n, random.Random(seed + 1))
    _, pretest = cohort(population(n, rng), truth, rng)
    offsets = calibrate(pretest)
    _, sessions = cohort(people, truth, rng, offsets=offsets)
    return Base(seed, truth, offsets, people, sessions)


def digest(payload: object) -> str:
    """SHA-256 of the printed numbers. Two runs with the same arguments print the same digest."""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode()).hexdigest()
