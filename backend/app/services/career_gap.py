"""Which one confirmed skill would close the most open vacancies. It does not change the grade."""
from __future__ import annotations


def career_gap(have: set[str], vacancies: list[set[str]]) -> dict | None:
    """The skill that is the only gap for the largest number of vacancies.

    A vacancy already covered, or one with two gaps, does not count. No such skill means no hint.
    """
    counts: dict[str, int] = {}
    considered = 0
    for wanted in vacancies:
        if not wanted:
            continue
        considered += 1
        missing = wanted - have
        if len(missing) == 1:
            skill = next(iter(missing))
            counts[skill] = counts.get(skill, 0) + 1
    if not counts:
        return None
    skill, gained = max(counts.items(), key=lambda item: (item[1], item[0]))
    return {"skill": skill, "gained": gained, "vacancies": considered}
