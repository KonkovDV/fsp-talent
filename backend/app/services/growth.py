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
