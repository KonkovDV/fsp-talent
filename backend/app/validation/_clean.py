"""The clean cohort of `app.validation.assessment.run`, rebuilt for the side studies."""
from __future__ import annotations

import random

from app.validation.assessment import Session, Truth, calibrate, cohort, population


def clean_sessions(n: int, seed: int) -> list[Session]:
    rng = random.Random(seed)
    truth = Truth.draw(rng)
    people = population(n, random.Random(seed + 1))
    population(max(300, n // 2), random.Random(seed + 2))
    _, pretest = cohort(population(n, rng), truth, rng)
    offsets = calibrate(pretest)
    _, sessions = cohort(people, truth, rng, offsets=offsets)
    return sessions
