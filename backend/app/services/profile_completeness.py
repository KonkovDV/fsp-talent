"""How much of the profile the match can use. Eight checks, a percent and the missing codes.

A missing FSP history is not a gap: the technical specification says a profile without it stays valid.
Hiding the city from the card is not a gap either. The city still counts once the candidate named it.
"""
from __future__ import annotations

_CHECKS = (
    ("email", "Email подтверждён", None),
    ("survey", "Опрос: направление и специализация", "/candidate/profile"),
    ("grade", "Грейд выбран", "/candidate/profile"),
    ("test", "Грейд подтверждён тестом", "/candidate/assessment"),
    ("skills", "В паспорте есть навык", "/candidate/profile"),
    ("salary", "Названо ожидание по зарплате", "/candidate/profile"),
    ("city", "Указан город", "/candidate/profile"),
    ("format", "Указан формат работы", "/candidate/profile"),
)


def profile_completeness(*, email_verified: bool, survey_done: bool, declared_grade: str | None,
                         assessed_grade: str | None, skill_count: int, salary_from: int | None,
                         salary_to: int | None, region: str | None, work_formats: list | tuple | None) -> dict:
    """Percent is half-up, so one check of eight is 13, not 12."""
    flags = {
        "email": bool(email_verified),
        "survey": bool(survey_done),
        "grade": bool(declared_grade or assessed_grade),
        "test": bool(assessed_grade),
        "skills": skill_count > 0,
        "salary": salary_from is not None or salary_to is not None,
        "city": bool((region or "").strip()),
        "format": bool(work_formats),
    }
    items = [
        {"code": code, "label": label, "done": flags[code], "href": None if flags[code] else href}
        for code, label, href in _CHECKS
    ]
    done = sum(1 for item in items if item["done"])
    total = len(items)
    return {
        "percent": (100 * done + total // 2) // total,
        "done": done,
        "total": total,
        "missing": [item["code"] for item in items if not item["done"]],
        "items": items,
    }
