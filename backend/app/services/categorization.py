"""
Rule-based categorization: role x grade x stack.

Grade and the FSP-verified level are independent axes: grade comes from a test result when there is
one, otherwise from the grade the candidate chose in the survey, never from experience or competition results.
Experience only suggests which grade to choose. An FSP discipline does not choose the specialization:
that comes from the survey, or from resume skills when the survey is still empty.
"""
from __future__ import annotations

from typing import TypedDict

from app.services.skills import ROLES, roles_for
from app.services.survey import SPECIALIZATIONS

RULES_VERSION = "v2.2.0"
# Shown until the survey picks a specialization and resume skills are too few to name one.
UNCHOSEN_ROLE = "не выбрана"
GRADES = ("intern", "junior", "middle", "senior", "lead")
MIN_SKILLS_FOR_ROLE = 2

DISCIPLINE_ROLE_MAP: dict[str, str] = {
    "algorithmic": "backend",
    "product": "fullstack",
    "security": "security",
    "bas": "embedded",
    "robotics": "embedded",
    "ai": "ml",
}
DISCIPLINE_LABELS = {
    "algorithmic": "Алгоритмическое программирование",
    "product": "Продуктовое программирование",
    "security": "Программирование систем ИБ",
    "bas": "Программирование БАС",
    "robotics": "Программирование робототехники",
    # Sixth discipline in the 2026 calendar (ЕКП): so far training events only, no official protocols yet.
    "ai": "Программирование систем ИИ",
}


class CategoryResult(TypedDict):
    primary_role: str
    grade: str
    grade_source: str
    stack: list[str]
    explanation: list[str]
    rules_version: str


def _ru_word(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    if n % 10 == 1:
        return one
    if 2 <= n % 10 <= 4:
        return few
    return many


def grade_from_experience(years: int | None) -> str:
    if years is None or years < 2:
        return "junior"
    if years < 5:
        return "middle"
    return "senior"


def assign_category(
    skills: list[str],
    discipline_scores: list[dict],
    experience_years: int | None = None,
    declared_grade: str | None = None,
    assessed_grade: str | None = None,
    specialization: str | None = None,
) -> CategoryResult:
    explanation: list[str] = []

    role_votes = {r: 0 for r in ROLES}
    for s in skills:
        for r in roles_for(s):
            role_votes[r] += 1
    best_skill_role = max(ROLES, key=lambda r: (role_votes[r], -ROLES.index(r)))

    if specialization in ROLES:
        # TZ 2.1: the survey decides the specialization; skills and FSP only explain it.
        role = specialization
        explanation.append(f"Специализация из опроса: {SPECIALIZATIONS.get(role, role)}")
    elif role_votes[best_skill_role] >= MIN_SKILLS_FOR_ROLE:
        role = best_skill_role
        count = role_votes[role]
        skills_word = _ru_word(count, "подтверждённый навык", "подтверждённых навыка", "подтверждённых навыков")
        explanation.append(f"Роль по навыкам: {count} {skills_word} направления {SPECIALIZATIONS.get(role, role)}")
    else:
        role = UNCHOSEN_ROLE
        explanation.append("Специализация не выбрана: пройдите опрос")

    if assessed_grade in GRADES:
        # Confirmed by a test: outranks the self-described grade and the experience estimate.
        grade, source = assessed_grade, "assessed"
        explanation.append("Грейд подтверждён тестом")
    elif declared_grade in GRADES:
        grade, source = declared_grade, "declared"
        explanation.append("Грейд указан кандидатом, тестом не подтверждён")
    else:
        # Q&A: the candidate chooses the grade. Experience is only a hint for that choice, never the grade.
        grade, source = "junior", "default"
        explanation.append("Грейд не выбран в опросе: до выбора карточка стоит как junior")
    if source != "assessed" and experience_years is not None:
        hint = grade_from_experience(experience_years)
        explanation.append(
            f"Подсказка по стажу ({experience_years} {_ru_word(experience_years, 'год', 'года', 'лет')}): "
            f"обычно это {hint}. Грейд даёт только тест")

    stack = sorted({s for s in skills if roles_for(s)})[:12]
    return CategoryResult(primary_role=role, grade=grade, grade_source=source, stack=stack,
                          explanation=explanation, rules_version=RULES_VERSION)
