"""
Rule-based categorization: role x grade x stack.

Grade priority (highest first):
  1. declared  -- candidate's own declaration (most trusted, candidate knows themselves)
  2. experience -- from experience_years (industry-standard proxy)
  3. competition -- from FSP-verified LCB when no experience data is available;
                    targets school students / young athletes with no work history
  4. default   -- 'junior' when all signals are absent

The competition-derived grade fills the gap for young FSP participants who
have real results but no industry experience to report.  It does NOT downgrade
candidates who have experience_years set: self-reported experience is a
different axis from competition performance and should not be overridden.
"""
from __future__ import annotations

from typing import TypedDict

from app.services.scoring.engine import grade_from_lcb
from app.services.skills import ROLES, roles_for

RULES_VERSION = "v2.0.0"
GRADES = ("junior", "middle", "senior", "lead")
MIN_SKILLS_FOR_ROLE = 2

DISCIPLINE_ROLE_MAP: dict[str, str] = {
    "algorithmic": "backend",
    "product": "fullstack",
    "security": "security",
    "bas": "embedded",
    "robotics": "embedded",
}
DISCIPLINE_LABELS = {
    "algorithmic": "Алгоритмическое программирование",
    "product": "Продуктовое программирование",
    "security": "Программирование систем ИБ",
    "bas": "Программирование БАС",
    "robotics": "Программирование робототехники",
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
) -> CategoryResult:
    explanation: list[str] = []

    role_votes = {r: 0 for r in ROLES}
    for s in skills:
        for r in roles_for(s):
            role_votes[r] += 1
    best_skill_role = max(ROLES, key=lambda r: (role_votes[r], -ROLES.index(r)))
    best_disc = max(discipline_scores, key=lambda d: d["lcb"], default=None)

    if role_votes[best_skill_role] >= MIN_SKILLS_FOR_ROLE:
        role = best_skill_role
        count = role_votes[role]
        skills_word = _ru_word(count, "подтверждённый навык", "подтверждённых навыка", "подтверждённых навыков")
        explanation.append(f"Роль по навыкам: {count} {skills_word} направления {role}")
    elif best_disc:
        role = DISCIPLINE_ROLE_MAP.get(best_disc["discipline"], "fullstack")
        explanation.append(f"Роль по дисциплине ФСП: {DISCIPLINE_LABELS.get(best_disc['discipline'], '')}")
    else:
        role = "fullstack"
        explanation.append("Роль по умолчанию: недостаточно данных")

    # --- Grade: declared > experience > competition > default ---
    if declared_grade in GRADES:
        grade, source = declared_grade, "declared"
        explanation.append("Грейд указан кандидатом")
    elif experience_years is not None:
        grade, source = grade_from_experience(experience_years), "experience"
        explanation.append(
            f"Грейд по опыту: {experience_years} "
            f"{_ru_word(experience_years, 'год', 'года', 'лет')}"
        )
    elif best_disc and (comp_grade := grade_from_lcb(best_disc["lcb"])):
        # Activated only when experience_years is None -- typically school-age athletes
        # who have no work history but a verified competition track record.
        # Uses the FSP-attested Wilson LCB as an objective competence proxy.
        grade, source = comp_grade, "competition"
        disc_label = DISCIPLINE_LABELS.get(best_disc["discipline"], best_disc["discipline"])
        explanation.append(
            f"Грейд по соревнованиям ФСП: LCB {best_disc['lcb']:.2f} "
            f"(дисциплина «{disc_label}»)"
        )
    else:
        grade, source = "junior", "default"
        explanation.append("Опыт не указан, грейд по умолчанию")

    stack = sorted({s for s in skills if roles_for(s)})[:12]
    return CategoryResult(primary_role=role, grade=grade, grade_source=source, stack=stack,
                          explanation=explanation, rules_version=RULES_VERSION)
