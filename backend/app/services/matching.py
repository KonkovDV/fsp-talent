"""Explainable match score of a candidate for an employer's need.

The score is a weighted mean of factors in [0, 1]. A factor that does not apply (the need names no skills,
the candidate has no FSP history) is dropped and the remaining weights are renormalised, so a candidate is
not punished for an axis the employer did not ask about, and a strong candidate without FSP history competes
on equal terms (TZ 2.1). Every factor leaves a plus, minus or info line for the card.

The same pure function ranks candidates in the API and in the offline evaluation
(app.validation.matching), so the published nDCG describes this code.
"""
from __future__ import annotations

from dataclasses import dataclass, field

GRADES = ("junior", "middle", "senior", "lead")

# Relevance (skills, grade, role) decides the order; evidence (test, FSP) breaks near-ties. A first version
# gave the test 0.15 and charged untested candidates the full amount: it lost to the keyword baseline on the
# offline benchmark (docs/VALIDATION_MATCHING.md), because a missing test is not evidence of a poor fit.
WEIGHTS = {
    "skills": 0.40,
    "grade": 0.25,
    "role": 0.15,
    "test": 0.08,
    "fsp": 0.05,
    "text": 0.04,
    "industry": 0.03,
}
UNTESTED = 0.5          # test factor of a candidate who has not taken the test: neutral, not zero
LABELS = {
    "skills": "Навыки", "grade": "Грейд", "test": "Тест", "role": "Специализация",
    "fsp": "Подтверждено ФСП", "text": "Совпадение с запросом", "industry": "Отрасль",
}
# How much a skill counts by the strength of evidence: roughly the probability that the skill is real.
# A bare declaration is still usually true, so it is discounted, not halved.
TRUST = {"test_confirmed": 1.0, "resume_confirmed": 0.95, "self_reported": 0.8}
RELATED_CREDIT = 0.3
# Groups of interchangeable technologies: knowing one gives partial credit for another.
RELATED = [
    {"PostgreSQL", "MySQL", "SQL", "ClickHouse"},
    {"React", "Vue.js", "Angular", "Next.js"},
    {"JavaScript", "TypeScript", "Node.js"},
    {"Django", "Flask", "FastAPI"},
    {"Java", "Kotlin", "Spring"},
    {"Go", "Rust", "C++"},
    {"C", "C++", "STM32", "Arduino", "RTOS"},
    {"PyTorch", "TensorFlow", "scikit-learn", "Machine Learning"},
    {"Docker", "Kubernetes"},
    {"Kafka", "RabbitMQ"},
    {"Pentesting", "Web Security", "CTF"},
    {"Swift", "Flutter", "Android", "Kotlin"},
]
ROLE_NEIGHBOURS = {
    "fullstack": {"backend", "frontend"}, "backend": {"fullstack", "devops"}, "frontend": {"fullstack", "mobile"},
    "mobile": {"frontend"}, "devops": {"backend", "security"}, "security": {"devops"},
    "ml": {"backend"}, "embedded": set(),
}
FSP_FULL_LCB = 0.6     # LCB at which the FSP factor saturates


@dataclass(frozen=True)
class NeedSpec:
    role: str | None = None
    grade: str | None = None
    skills: tuple[str, ...] = ()          # required
    nice: tuple[str, ...] = ()            # nice to have: half weight
    industry: str | None = None
    text: bool = False                    # a free-text query was given


@dataclass
class CandidateFacts:
    role: str | None
    grade: str | None
    grade_source: str | None              # assessed | declared | experience | default
    skills: dict[str, str] = field(default_factory=dict)   # name -> trust level
    test_p: float | None = None           # P(level) of the confirmation for this specialization
    test_spec: str | None = None
    fsp_lcb: float | None = None          # None: no FSP history
    industry: str | None = None
    text_rank: float = 0.0                # 0..1 lexical relevance, normalised inside the pool


@dataclass(frozen=True)
class Factor:
    key: str
    label: str
    weight: float
    value: float | None                   # None: not applicable


@dataclass
class MatchResult:
    score: float
    factors: list[Factor]
    plus: list[str]
    minus: list[str]
    info: list[str]


def _related(skill: str, have: dict[str, str]) -> str | None:
    for group in RELATED:
        if skill in group:
            for other in sorted(group - {skill}):
                if other in have:
                    return other
    return None


def _skill_credit(skill: str, have: dict[str, str]) -> tuple[float, str]:
    if skill in have:
        trust = have[skill]
        return TRUST.get(trust, 0.6), trust
    other = _related(skill, have)
    if other:
        return RELATED_CREDIT * TRUST.get(have[other], 0.6), f"related:{other}"
    return 0.0, "missing"


def score(need: NeedSpec, c: CandidateFacts, use_trust: bool = True, use_test: bool = True,
          use_fsp: bool = True, use_related: bool = True) -> MatchResult:
    """Factor score with plus / minus / info lines. The use_* switches exist for the ablation study."""
    values: dict[str, float | None] = {k: None for k in WEIGHTS}
    plus: list[str] = []
    minus: list[str] = []
    info: list[str] = []

    wanted = [(s, 1.0) for s in need.skills] + [(s, 0.5) for s in need.nice if s not in need.skills]
    if wanted:
        total = got = 0.0
        confirmed, related, missing = [], [], []
        for skill, w in wanted:
            credit, how = _skill_credit(skill, c.skills)
            if not use_trust and credit > 0 and not how.startswith("related"):
                credit = 1.0
            if not use_related and how.startswith("related"):
                credit = 0.0
            total += w
            got += w * credit
            if how == "test_confirmed":
                confirmed.append(skill)
            elif how.startswith("related") and credit > 0:
                related.append(f"{skill} ≈ {how.split(':', 1)[1]}")
            elif how == "missing" and w == 1.0:
                missing.append(skill)
        values["skills"] = got / total
        have_n = sum(1 for s, w in wanted if w == 1.0 and s in c.skills)
        if need.skills:
            plus.append(f"Навыки: {have_n} из {len(need.skills)} обязательных")
        if confirmed:
            plus.append("Подтверждены тестом: " + ", ".join(confirmed))
        if related:
            info.append("Близкие технологии (частичный зачёт): " + ", ".join(related))
        if missing:
            minus.append("Нет навыков: " + ", ".join(missing))

    if need.grade in GRADES and c.grade in GRADES:
        gap = GRADES.index(c.grade) - GRADES.index(need.grade)
        base = {0: 1.0, 1: 0.6, -1: 0.35}.get(gap, 0.0)
        assessed = c.grade_source == "assessed"
        values["grade"] = base * (1.0 if assessed or not use_test else 0.85)
        if gap == 0:
            tail = " подтверждён тестом" if assessed else " указан кандидатом, тестом не подтверждён"
            (plus if assessed else info).append(f"Грейд {c.grade}{tail}")
        elif gap > 0:
            info.append(f"Грейд выше запрошенного: {c.grade}")
        else:
            minus.append(f"Грейд ниже запрошенного: {c.grade}")

    if use_test:
        if c.test_p is not None and (need.role is None or c.test_spec in (None, need.role)):
            values["test"] = c.test_p
            plus.append(f"Тест: вероятность уровня {round(c.test_p * 100)}%")
        else:
            values["test"] = UNTESTED
            if not any("тестом не подтверждён" in line for line in info):
                info.append("Грейд не проверен тестом")

    if need.role:
        if c.role == need.role:
            values["role"] = 1.0
        elif c.role in ROLE_NEIGHBOURS.get(need.role, set()):
            values["role"] = 0.5
            info.append(f"Смежная специализация: {c.role}")
        else:
            values["role"] = 0.0
            minus.append(f"Другая специализация: {c.role or 'не указана'}")

    if use_fsp:
        if c.fsp_lcb is None:
            info.append("Нет истории ФСП — ось не учитывается и не штрафует")
        else:
            values["fsp"] = min(1.0, max(0.0, c.fsp_lcb / FSP_FULL_LCB))
            if values["fsp"] >= 0.5:
                plus.append(f"Подтверждённый уровень ФСП (нижняя граница {c.fsp_lcb:.2f})")

    if need.text:
        values["text"] = max(0.0, min(1.0, c.text_rank))

    if need.industry and need.industry != "any":
        values["industry"] = 1.0 if c.industry in (need.industry, "any") else 0.0
        if values["industry"] == 1.0 and c.industry == need.industry:
            plus.append("Интересна ваша отрасль")

    factors = [Factor(k, LABELS[k], WEIGHTS[k], values[k]) for k in WEIGHTS]
    active = [f for f in factors if f.value is not None]
    weight = sum(f.weight for f in active)
    total = sum(f.weight * f.value for f in active) / weight if weight else 0.0
    return MatchResult(round(total, 4), factors, plus, minus, info)


def recommended_categories(rows: list[tuple[str | None, str | None, float]], top: int = 3) -> list[dict]:
    """Which role × grade cells hold the best matches: (role, grade, score) -> cells by mean score of the top."""
    cells: dict[tuple[str | None, str | None], list[float]] = {}
    for role, grade, s in rows:
        cells.setdefault((role, grade), []).append(s)
    ranked = sorted(cells.items(), key=lambda kv: (-sum(sorted(kv[1])[-5:]) / min(5, len(kv[1])), -len(kv[1])))
    return [{"role": r, "grade": g, "candidates": len(v), "best": round(max(v), 3)} for (r, g), v in ranked[:top]]
