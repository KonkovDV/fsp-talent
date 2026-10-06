"""
Rule-based categorization: role x grade x stack.

Grade and the FSP-verified level are independent axes: grade comes from a test result when there is
one, otherwise from the candidate's declaration or experience, never from competition results.
"""
from __future__ import annotations

from typing import TypedDict

from app.services.skills import ROLES, roles_for
from app.services.survey import SPECIALIZATIONS

RULES_VERSION = "v2.1.0"
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
    best_disc = max(discipline_scores, key=lambda d: d["lcb"], default=None)

    if specialization in ROLES:
        # TZ 2.1: the survey decides the specialization; skills and FSP only explain it.
        role = specialization
        explanation.append(f"Специализация из опроса: {SPECIALIZATIONS.get(role, role)}")
    elif role_votes[best_skill_role] >= MIN_SKILLS_FOR_ROLE:
        role = best_skill_role
        count = role_votes[role]
        skills_word = _ru_word(count, "подтверждённый навык", "подтверждённых навыка", "подтверждённых навыков")
        explanation.append(f"Роль по навыкам: {count} {skills_word} направления {SPECIALIZATIONS.get(role, role)}")
    elif best_disc:
        role = DISCIPLINE_ROLE_MAP.get(best_disc["discipline"], "fullstack")
        explanation.append(f"Роль по дисциплине ФСП: {DISCIPLINE_LABELS.get(best_disc['discipline'], '')}")
    else:
        role = "fullstack"
        explanation.append("Роль по умолчанию: недостаточно данных")

    if assessed_grade in GRADES:
        # Confirmed by a test: outranks the self-described grade and the experience estimate.
        grade, source = assessed_grade, "assessed"
        explanation.append("Грейд подтверждён тестом")
    elif declared_grade in GRADES:
        grade, source = declared_grade, "declared"
        explanation.append("Грейд указан кандидатом, тестом не подтверждён")
    elif experience_years is not None:
        grade, source = grade_from_experience(experience_years), "experience"
        explanation.append(
            f"Грейд по опыту: {experience_years} {_ru_word(experience_years, 'год', 'года', 'лет')}")
    else:
        grade, source = "junior", "default"
        explanation.append("Опыт не указан, грейд по умолчанию")

    stack = sorted({s for s in skills if roles_for(s)})[:12]
    return CategoryResult(primary_role=role, grade=grade, grade_source=source, stack=stack,
                          explanation=explanation, rules_version=RULES_VERSION)
