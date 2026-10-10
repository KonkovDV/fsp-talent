"""A soft line for an intern or a junior. Two signs are enough. The grade and the score stay put."""
from __future__ import annotations


def ambition_note(grade: str | None, job_search: str | None, skills: dict[str, str],
                  work_goal: str | None) -> str | None:
    if grade not in ("intern", "junior"):
        return None
    signs = 0
    if job_search == "active":
        signs += 1
    if len(skills) >= 4:
        signs += 1
    if any(level == "test_confirmed" for level in skills.values()):
        signs += 1
    if grade == "intern" and work_goal in ("job", "both"):
        signs += 1
    if signs < 2:
        return None
    return "Несколько признаков роста. Грейд от этой строки не меняется."
