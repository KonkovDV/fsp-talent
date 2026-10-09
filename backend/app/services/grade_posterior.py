"""Expected relevance of a shown grade when the true grade is still uncertain.

rel(Δ) is the same step table the legacy score uses: 1.0 on the requested grade, 0.6 one above,
0.35 one below, and 0 further away. The new factor is the expectation of that table.

A confirmed grade puts mass on the shown grade, one below and, when the session recommended
the next grade, one above. A declared grade puts mass π on one below and 1 − π on the shown
grade. π is the share who fail the first attempt at that grade, smoothed toward the overall
share. The simulation estimates it on seed 2029 only. The product reads the same shape from Redis
after the nightly job.
"""
from __future__ import annotations

GRADES = ("intern", "junior", "middle", "senior", "lead")
REL = {0: 1.0, 1: 0.6, -1: 0.35}
PI_M = 20
PI_SEED = 2029
REDIS_KEY = "grade-fail-rates"
PASS_P = 0.75


def grade_rel(delta: int) -> float:
    return REL.get(delta, 0.0)


def smooth_pi(fails: int, attempts: int, overall: float, m: int = PI_M) -> float:
    """(k + m·π₀) / (n + m). With no local attempts this is the overall share."""
    return (fails + m * overall) / (attempts + m)


def mass_assessed(shown: str, p_pass: float, p_up: float) -> dict[int, float]:
    """P(G = s−1), P(G = s), P(G = s+1). They sum to 1."""
    s = GRADES.index(shown)
    p_pass = min(max(p_pass, 0.0), 1.0)
    p_up = min(max(p_up, 0.0), p_pass)
    if s + 1 >= len(GRADES):
        p_up = 0.0
    return {s - 1: 1.0 - p_pass, s: p_pass - p_up, s + 1: p_up}


def mass_declared(shown: str, pi: float) -> dict[int, float]:
    s = GRADES.index(shown)
    pi = min(max(pi, 0.0), 1.0)
    return {s - 1: pi, s: 1.0 - pi}


def expected_rel(need: str, mass: dict[int, float]) -> float:
    need_i = GRADES.index(need)
    return sum(weight * grade_rel(grade_i - need_i) for grade_i, weight in mass.items())


def fail_table(attempts: list[tuple[str, str, bool]]) -> tuple[float, dict[tuple[str, str], float]]:
    """attempts are (role, declared grade, passed the first try)."""
    if not attempts:
        return 0.0, {}
    fails = sum(1 for _, _, passed in attempts if not passed)
    overall = fails / len(attempts)
    cells: dict[tuple[str, str], list[int]] = {}
    for role, grade, passed in attempts:
        bucket = cells.setdefault((role, grade), [0, 0])
        bucket[1] += 1
        if not passed:
            bucket[0] += 1
    return overall, {key: smooth_pi(k, n, overall) for key, (k, n) in cells.items()}


def lookup_pi(overall: float, cells: dict[tuple[str, str], float], role: str | None, grade: str | None) -> float:
    if role and grade and (role, grade) in cells:
        return cells[(role, grade)]
    return overall


async def read_fail_rates() -> tuple[float, dict[tuple[str, str], float]] | None:
    import json

    from app.core.redis_client import get_redis

    try:
        raw = await (await get_redis()).get(REDIS_KEY)
    except Exception:
        return None
    if not raw:
        return None
    data = json.loads(raw)
    cells = {}
    for key, value in data.get("cells", {}).items():
        role, _, grade = key.partition("|")
        if grade:
            cells[(role, grade)] = float(value)
    return float(data["pi0"]), cells


async def write_fail_rates(overall: float, cells: dict[tuple[str, str], float]) -> None:
    import json

    from app.core.redis_client import get_redis

    if not cells:
        return
    payload = {
        "pi0": overall,
        "cells": {f"{role}|{grade}": value for (role, grade), value in cells.items()},
    }
    await (await get_redis()).set(REDIS_KEY, json.dumps(payload))


async def measure_fail_rates(db) -> tuple[float, dict[tuple[str, str], float]]:
    from sqlalchemy import select

    from app.models.assessment import TestSession

    rows = (await db.execute(
        select(TestSession.participant_id, TestSession.specialization, TestSession.target_grade,
               TestSession.p_pass, TestSession.flags)
        .where(TestSession.status == "completed", TestSession.specialization.is_not(None))
        .order_by(TestSession.started_at)
    )).all()
    first: dict[tuple, tuple[str, str, bool]] = {}
    for pid, spec, grade, p_pass, flags in rows:
        if (flags or {}).get("vacancy_id"):
            continue
        key = (pid, spec, grade)
        if key not in first:
            first[key] = (spec, grade, p_pass is not None and p_pass >= PASS_P)
    return fail_table(list(first.values()))
