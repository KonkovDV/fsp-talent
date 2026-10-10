"""Skills the next grade already names and this profile does not.

A skill is shown only when at least MIN_PEOPLE in that grade named it, and only when the
skill belongs to the candidate's specialization. A thinner grade is omitted entirely.
Nothing here changes the grade: the grade still comes only from the test.
"""
from __future__ import annotations

from app.services.categorization import GRADES
from app.services.skills import roles_for

MIN_PEOPLE = 5
MAX_GAPS = 5
MAX_REACH = 5


def next_grade(grade: str | None) -> str | None:
    if grade not in GRADES:
        return None
    index = GRADES.index(grade)
    if index + 1 >= len(GRADES):
        return None
    return GRADES[index + 1]


def growth_gaps(role: str | None, owned: set[str], counts: dict[str, int], people: int) -> list[dict]:
    """Up to MAX_GAPS missing skills, most named first. Empty when the grade is too small."""
    if not role or people < MIN_PEOPLE:
        return []
    gaps = []
    for name, named in counts.items():
        if named < MIN_PEOPLE or name in owned:
            continue
        if role not in roles_for(name):
            continue
        gaps.append({"skill": name, "people": named})
    gaps.sort(key=lambda item: (-item["people"], item["skill"]))
    return gaps[:MAX_GAPS]


def skill_reach(role: str | None, owned: set[str], needs: list[tuple[str | None, list[str]]]) -> list[dict]:
    """Open needs of this specialization that are one required skill away.

    A need counts for that skill only when every other required skill is already named.
    Nice-to-have skills are not required. The grade and the match score are not inputs.
    """
    if not role:
        return []
    counts: dict[str, int] = {}
    for need_role, skills in needs:
        if need_role != role:
            continue
        required = [name for name in skills if name]
        missing = [name for name in required if name not in owned]
        if len(missing) != 1:
            continue
        skill = missing[0]
        if role not in roles_for(skill):
            continue
        counts[skill] = counts.get(skill, 0) + 1
    rows = [{"skill": name, "needs": count} for name, count in counts.items()]
    rows.sort(key=lambda item: (-item["needs"], item["skill"]))
    return rows[:MAX_REACH]
