"""Which one confirmed skill would close the most open vacancies. It does not change the grade.

The hint stays closed until several different companies have opened the card, so one viewer
does not read a statistic built from the open market.
"""
from __future__ import annotations

from app.services.matching import IMPLIES

INTEREST_MIN = 3


def _covered(have: set[str]) -> set[str]:
    """Confirmed names plus the general skills a narrower confirmed tool implies."""
    out = set(have)
    for tool, targets in IMPLIES.items():
        if tool in have:
            out.update(targets)
    return out


def career_gap(have: set[str], vacancies: list[set[str]]) -> dict | None:
    """The skill that is the only gap for the largest number of vacancies.

    A vacancy already covered, or one with two gaps, does not count. A narrower tool
    that implies the named skill is not a gap. No such skill means no hint.
    """
    known = _covered(have)
    counts: dict[str, int] = {}
    considered = 0
    for wanted in vacancies:
        if not wanted:
            continue
        considered += 1
        missing = wanted - known
        if len(missing) == 1:
            skill = next(iter(missing))
            counts[skill] = counts.get(skill, 0) + 1
    if not counts:
        return None
    skill, gained = max(counts.items(), key=lambda item: (item[1], item[0]))
    return {"skill": skill, "gained": gained, "vacancies": considered}


def career_hint(have: set[str], vacancies: list[set[str]], companies: int) -> dict:
    """Same hint, hidden until ``INTEREST_MIN`` different companies have opened the card."""
    base = career_gap(have, vacancies)
    considered = base["vacancies"] if base else sum(1 for wanted in vacancies if wanted)
    if companies < INTEREST_MIN:
        return {
            "skill": None, "gained": 0, "vacancies": considered,
            "open": False, "need_companies": INTEREST_MIN,
        }
    if base is None:
        return {"skill": None, "gained": 0, "vacancies": considered, "open": True}
    return {**base, "open": True}
