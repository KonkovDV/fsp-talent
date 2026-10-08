"""Explainable match score of a candidate for an employer's need.

The score is a weighted mean of factors in [0, 1]. A factor that does not apply (the need names no skills,
the candidate has no FSP history) is dropped and the remaining weights are renormalised, so a candidate is
not punished for an axis the employer did not ask about, and a strong candidate without FSP history competes
on equal terms (TZ 2.1). Every factor leaves a plus, minus or info line for the card.

The same pure function ranks candidates in the API and in the offline evaluation
(app.validation.matching), so the published nDCG describes this code.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, replace

from app.services.survey import SPECIALIZATIONS

GRADES = ("intern", "junior", "middle", "senior", "lead")
GRADE_RU = {"intern": "стажёр", "junior": "джуниор", "middle": "мидл", "senior": "сеньор", "lead": "лид"}

# Fit to the need (skills, grade, role) decides who belongs in the list. Evidence (test and FSP) decides
# the order inside the category: it is added with EVIDENCE_WEIGHT, scaled by how close the candidate is to the
# requested role and grade, so a strong profile from another category is not pulled over a matching one,
# while inside the category a passed test and FSP results outrank one more self-described skill (TZ section 2).
# A missing FSP history is omitted, not scored as zero. docs/VALIDATION_MATCHING.md has the ablations.
FIT_KEYS = ("skills", "grade", "role", "text", "industry")
EVIDENCE_KEYS = ("test", "fsp")
WEIGHTS = {
    "skills": 0.50,
    "grade": 0.20,
    "role": 0.20,
    "text": 0.05,
    "industry": 0.05,
    "test": 0.50,
    "fsp": 0.50,
}
UNTESTED = 0.20
# Weight of the evidence next to the fit (fit has weight 1).
EVIDENCE_WEIGHT = 0.40
# Width of one fit tier, used only while USE_FIT_TIERS is on.
# Sweep on 07.10.2026, seeds 2026–2028, 800 candidates and 80 needs:
# `python -m app.validation.matching --tier-delta 0.02,0.03,0.05,0.08,0.10`
# Only 0.02 kept nDCG(full) within 0.005 of nDCG(no evidence), and it dropped
# Spearman to 0.098 and raised overclaim to 24.3 %. That misses Spearman ≥ 0.22
# and overclaim ≤ 20 %, so the product order does not use tiers.
FIT_TIER_DELTA = 0.05
USE_FIT_TIERS = False
# A grade the candidate only declared counts for this share of a grade the test confirmed.
DECLARED_GRADE = 0.85
# Half of the evidence lift is always there inside the category, the other half follows skill coverage:
# a candidate without the requested skills is not lifted over one who has them by test results alone.
SKILL_GATE = 0.5
LABELS = {
    "skills": "Навыки", "grade": "Грейд", "test": "Тест", "role": "Специализация",
    "fsp": "ФСП", "text": "Запрос", "industry": "Предметная область",
}
TRUST = {"test_confirmed": 1.0, "resume_confirmed": 0.75, "self_reported": 0.55}
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
    {"pytest", "Playwright", "Selenium"},
    {"Airflow", "Spark"},
    {"Swift", "Flutter", "Android", "Kotlin"},
]
ROLE_NEIGHBOURS = {
    "fullstack": {"backend", "frontend", "qa"}, "backend": {"fullstack", "devops", "qa", "analyst", "data"},
    "frontend": {"fullstack", "mobile"},
    "mobile": {"frontend"}, "devops": {"backend", "security", "data"}, "security": {"devops"},
    "ml": {"backend", "analyst", "data"}, "embedded": set(),
    "qa": {"backend", "fullstack"}, "analyst": {"backend", "ml", "data"},
    "data": {"backend", "ml", "devops"},
}


def category_band(role: str | None, grade: str | None,
                  need_role: str | None, need_grade: str | None) -> int:
    """0 exact category, 1 one step away or a neighbour at the exact grade, 2 the rest.

    The band is the category the employer sees. A competition result does not move it.
    The product order does not use this; the measurement does.
    """
    if not need_role or not need_grade or not role or not grade:
        return 2
    if grade not in GRADES or need_grade not in GRADES:
        return 2
    gap = abs(GRADES.index(grade) - GRADES.index(need_grade))
    if role == need_role and gap == 0:
        return 0
    neighbour = role in ROLE_NEIGHBOURS.get(need_role, set())
    if (role == need_role and gap == 1) or (neighbour and gap == 0):
        return 1
    return 2


FSP_FULL_LCB = 0.6     # LCB at which the FSP factor saturates
# Pending invitations a candidate may hold before the list steps them down. The step is small
# and capped, so a strong fit is not buried by a busy inbox.
OPEN_INVITE_FREE = 2
CONGESTION_STEP = 0.02
CONGESTION_CAP = 0.10
# One earlier refusal over pay lowers P(accept). Three is the cap, so a long history cannot zero it.
SALARY_REFUSAL_FACTOR = 0.85
SALARY_REFUSAL_CAP = 3
# Latest interview with this company, applied only when both sides named a salary.
# A pass can lift P(accept) up to 1. A fail and a no-show lower it. No interview leaves the score as it is.
INTERVIEW_FACTOR = {"passed": 1.10, "failed": 0.85, "no_show": 0.70}
REASON_SOURCE = {
    "VERIFIED_SKILL": "тест", "TEST_SCORE": "тест", "UNTESTED": "тест",
    "FSP_BONUS": "ФСП", "FSP_SCORE": "ФСП", "FSP_NEUTRAL": "ФСП",
    "GRADE_DECLARED": "заявлено", "SKILL_COVERAGE": "заявлено", "SKILL_GAP": "заявлено",
    "RELATED_SKILL": "заявлено",
    "PAY_FIT": "вилка", "PAY_LOW": "вилка", "PAY_GAP": "вилка", "SALARY_HISTORY": "вилка",
    "CONGESTION": "очередь",
    "JOB_SEARCH_ACTIVE": "профиль", "JOB_SEARCH_OPEN": "профиль",
    "INTERVIEW_PASSED": "собеседование", "INTERVIEW_FAILED": "собеседование",
    "INTERVIEW_NO_SHOW": "собеседование",
}


@dataclass(frozen=True)
class NeedSpec:
    role: str | None = None
    grade: str | None = None
    skills: tuple[str, ...] = ()          # required
    nice: tuple[str, ...] = ()            # nice to have: half weight
    industry: str | None = None
    text: bool = False                    # a free-text query was given
    salary_from: int | None = None        # gross, optional; with the candidate's wish it is P(accept)
    salary_to: int | None = None


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
    salary_from: int | None = None        # gross wish; None: the candidate did not name one
    salary_to: int | None = None
    test_se: float | None = None          # posterior SE; when set, the test factor uses θ̂ − 1.64·SE
    test_correct: int | None = None       # right answers in the confirming session
    test_n: int | None = None             # answers in that session; with test_correct, Wilson enters the rank
    open_invites: int = 0                 # pending invitations; above the free allowance the card steps down
    salary_refusals: int = 0              # earlier declines whose reason was the pay band
    job_search: str = "open"              # active | open | not_looking; open multiplies P(accept) by 0.8
    interview_outcome: str | None = None  # passed | failed | no_show with this company; None leaves P(accept)


@dataclass(frozen=True)
class Factor:
    key: str
    label: str
    weight: float
    value: float | None                   # None: not applicable


@dataclass(frozen=True)
class Reason:
    """One line of the explanation. `code` is stable; the Russian `text` is what the card shows."""
    code: str
    text: str
    tone: str   # plus | minus | info
    points: float | None = None   # contribution to the employer score, 0..1; set for the test and FSP lines


@dataclass
class MatchResult:
    score: float
    factors: list[Factor]
    plus: list[str]
    minus: list[str]
    info: list[str]
    # "fit": the need names criteria and the score measures them. "evidence": no criteria at all,
    # so the score is the strength of the confirmed profile (test, FSP) and the UI says so.
    basis: str = "fit"
    reasons: list[Reason] = field(default_factory=list)
    fit: float | None = None          # weighted mean of the need-fit factors; None when the need names nothing
    tier: int | None = None           # floor(fit / FIT_TIER_DELTA); None when there is no fit
    confirmed: int = 0                # 1 when the shown grade comes from the test


def reason_source(code: str) -> str | None:
    return REASON_SOURCE.get(code)


def fit_tier(fit: float, delta: float | None = None) -> int:
    """Tier index of a fit in [0, 1]. A hair above the cut stays in the upper tier."""
    step = FIT_TIER_DELTA if delta is None else delta
    if step <= 0:
        return 0
    return int(math.floor((fit + 1e-9) / step))


def tier_ceiling(delta: float | None = None) -> int:
    return fit_tier(1.0, delta)


def wilson_lower(successes: int, n: int, z: float = 1.96) -> float | None:
    """Lower end of the Wilson interval for a count of successes.

    The test factor uses it when the session recorded how many answers were right. The probit
    bound θ̂ − z·SE is still applied when the posterior SE is known; the factor keeps the lower
    of the two. Topic shares on the result screen use the same interval and do not order the list.
    """
    if n <= 0:
        return None
    p = successes / n
    z2 = z * z
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return max(0.0, (centre - margin) / (1 + z2 / n))


def pass_lower_bound(p: float, z: float = 1.64) -> float:
    """P(θ ≥ cut) evaluated at θ̂ − z·SE. The SE cancels, so only the point probability is needed."""
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    law = statistics.NormalDist()
    return law.cdf(law.inv_cdf(p) - z)


def _note(bucket: list[str], reasons: list[Reason], tone: str, code: str, text: str) -> None:
    bucket.append(text)
    reasons.append(Reason(code, text, tone))


EVIDENCE_REASONS = {"test": ("TEST_SCORE", "UNTESTED"), "fsp": ("FSP_BONUS", "FSP_SCORE")}


def _with_points(reasons: list[Reason], factors: list[Factor], scale: float) -> list[Reason]:
    """Attach to the test and FSP lines how much each moved the score, so the card shows the contribution."""
    present = [f for f in factors if f.key in EVIDENCE_KEYS and f.value is not None]
    total = sum(f.weight for f in present)
    if not total:
        return reasons
    points = {f.key: scale * f.weight / total * f.value for f in present}
    out = []
    for r in reasons:
        key = next((k for k, codes in EVIDENCE_REASONS.items() if r.code in codes), None)
        out.append(replace(r, points=round(points[key], 3)) if key in points else r)
    return out


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
    reasons: list[Reason] = []

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
            _note(plus, reasons, "plus", "SKILL_COVERAGE",
                  f"Навыки: {have_n} из {len(need.skills)} обязательных")
        if confirmed:
            _note(plus, reasons, "plus", "VERIFIED_SKILL", "Подтверждены тестом: " + ", ".join(confirmed))
        if related:
            _note(info, reasons, "info", "RELATED_SKILL",
                  "Близкие технологии (частичный зачёт): " + ", ".join(related))
        if missing:
            _note(minus, reasons, "minus", "SKILL_GAP", "Нет навыков: " + ", ".join(missing))

    closeness = 1.0   # 1 inside the requested category; evidence weighs less the further the candidate is from it
    if need.grade in GRADES and c.grade in GRADES:
        gap = GRADES.index(c.grade) - GRADES.index(need.grade)
        base = {0: 1.0, 1: 0.6, -1: 0.35}.get(gap, 0.0)
        closeness *= base
        assessed = c.grade_source == "assessed"
        values["grade"] = base * (1.0 if assessed or not use_test else DECLARED_GRADE)
        if gap == 0:
            tail = " подтверждён тестом" if assessed else " указан кандидатом, тестом не подтверждён"
            text = f"Грейд «{GRADE_RU[c.grade]}»{tail}"
            if assessed:
                _note(plus, reasons, "plus", "CATEGORY_MATCH", text)
            else:
                _note(info, reasons, "info", "GRADE_DECLARED", text)
        elif gap > 0:
            _note(info, reasons, "info", "GRADE_ABOVE", f"Грейд выше запрошенного: {GRADE_RU[c.grade]}")
        else:
            _note(minus, reasons, "minus", "GRADE_BELOW", f"Грейд ниже запрошенного: {GRADE_RU[c.grade]}")

    if use_test:
        if c.test_p is not None and (need.role is None or c.test_spec in (None, need.role)):
            shown = c.test_p
            wilson = wilson_lower(c.test_correct, c.test_n) if c.test_correct is not None and c.test_n else None
            if c.test_se is not None and c.test_se > 0:
                shown = pass_lower_bound(c.test_p)
            if wilson is not None and shown != c.test_p:
                shown = min(shown, wilson)
            elif wilson is not None:
                shown = wilson
            if shown != c.test_p:
                _note(plus, reasons, "plus", "TEST_SCORE",
                      f"Тест: нижняя граница уровня {round(shown * 100)} % "
                      f"(точечная оценка {round(c.test_p * 100)} %)")
            else:
                _note(plus, reasons, "plus", "TEST_SCORE", f"Тест: вероятность уровня {round(c.test_p * 100)}%")
            values["test"] = shown
        else:
            values["test"] = UNTESTED
            if not any("тестом не подтверждён" in line for line in info):
                _note(info, reasons, "info", "UNTESTED", "Грейд не проверен тестом")

    if need.role:
        if c.role == need.role:
            values["role"] = 1.0
            _note(plus, reasons, "plus", "CATEGORY_MATCH",
                  f"Специализация совпадает: {SPECIALIZATIONS.get(c.role, c.role)}")
        elif c.role in ROLE_NEIGHBOURS.get(need.role, set()):
            values["role"] = 0.5
            _note(info, reasons, "info", "RELATED_ROLE",
                  f"Смежная специализация: {SPECIALIZATIONS.get(c.role, c.role)}")
        else:
            values["role"] = 0.0
            label = SPECIALIZATIONS.get(c.role, c.role) if c.role else "не указана"
            _note(minus, reasons, "minus", "OTHER_ROLE", f"Другая специализация: {label}")

    if use_fsp:
        if c.fsp_lcb is None:
            _note(info, reasons, "info", "FSP_NEUTRAL", "Нет истории ФСП — ось не учитывается и не штрафует")
        else:
            values["fsp"] = min(1.0, max(0.0, c.fsp_lcb / FSP_FULL_LCB))
            if values["fsp"] >= 0.5:
                _note(plus, reasons, "plus", "FSP_BONUS",
                      f"Подтверждённый уровень ФСП (нижняя граница {c.fsp_lcb:.2f})")
            else:
                _note(info, reasons, "info", "FSP_SCORE", f"Результаты ФСП учтены (нижняя граница {c.fsp_lcb:.2f})")

    if need.text:
        values["text"] = max(0.0, min(1.0, c.text_rank))

    if need.industry and need.industry != "any":
        values["industry"] = 1.0 if c.industry in (need.industry, "any") else 0.0
        if values["industry"] == 1.0 and c.industry == need.industry:
            _note(plus, reasons, "plus", "INDUSTRY", "Интересна ваша предметная область")

    factors = [Factor(k, LABELS[k], WEIGHTS[k], values[k]) for k in (*FIT_KEYS, *EVIDENCE_KEYS)]
    fit = _mean([f for f in factors if f.key in FIT_KEYS])
    evidence = _mean([f for f in factors if f.key in EVIDENCE_KEYS])
    if fit is None:
        # Nothing to match against (an empty search): rank by how well the profile is confirmed.
        employer, basis = evidence or 0.0, "evidence"
    else:
        # Inside one category the evidence decides: a test and FSP results outrank a self-described resume.
        if values["role"] is not None:
            closeness *= values["role"]
        if values["skills"] is not None:
            closeness *= (1.0 - SKILL_GATE) + SKILL_GATE * values["skills"]
        lift = EVIDENCE_WEIGHT * (evidence or 0.0) * closeness
        employer = (fit + lift) / (1.0 + EVIDENCE_WEIGHT)
        reasons = _with_points(reasons, factors, EVIDENCE_WEIGHT * closeness / (1.0 + EVIDENCE_WEIGHT))
        basis = "fit"
    accept = accept_probability(need.salary_from, need.salary_to, c.salary_from, c.salary_to)
    if accept is not None and c.salary_refusals > 0:
        accept *= SALARY_REFUSAL_FACTOR ** min(c.salary_refusals, SALARY_REFUSAL_CAP)
        _note(info, reasons, "info", "SALARY_HISTORY", "Раньше отказ был из-за вилки")
    if accept is not None:
        # The pay line describes the bands. The job-search factor is applied after it.
        floor = c.salary_from if c.salary_from is not None else c.salary_to
        ceiling = need.salary_to if need.salary_to is not None else need.salary_from
        if accept >= 1.0:
            _note(plus, reasons, "plus", "PAY_FIT", "Вилка покрывает ожидание кандидата")
        elif floor and ceiling:
            short = round(100 * (floor - ceiling) / floor)
            _note(minus if accept < 0.5 else info, reasons, "minus" if accept < 0.5 else "info",
                  "PAY_GAP" if accept < 0.5 else "PAY_LOW",
                  f"Вилка ниже ожидания примерно на {short} %")
    if c.job_search == "open" and accept is not None:
        accept *= 0.8
    if accept is not None and c.interview_outcome in INTERVIEW_FACTOR:
        accept = min(1.0, accept * INTERVIEW_FACTOR[c.interview_outcome])
        _note(info, reasons, "info",
              {"passed": "INTERVIEW_PASSED", "failed": "INTERVIEW_FAILED",
               "no_show": "INTERVIEW_NO_SHOW"}[c.interview_outcome],
              {"passed": "Собеседование с этой компанией пройдено",
               "failed": "Собеседование с этой компанией не пройдено",
               "no_show": "На собеседование с этой компанией не пришёл"}[c.interview_outcome])
    if c.job_search == "active":
        _note(plus, reasons, "plus", "JOB_SEARCH_ACTIVE", "Активно ищет")
    elif c.job_search == "open":
        _note(info, reasons, "info", "JOB_SEARCH_OPEN", "Открыт к предложениям")
    total = employer
    if accept is not None:
        # Reciprocal score: harmonic mean of "the employer would invite" and "the candidate would accept".
        # Absent on either side, the factor is omitted and the ranking stays the employer-only score.
        total = _harmonic(employer, accept)
    if c.open_invites > OPEN_INVITE_FREE:
        penalty = min(CONGESTION_CAP, CONGESTION_STEP * (c.open_invites - OPEN_INVITE_FREE))
        total = max(0.0, total - penalty)
        _note(info, reasons, "info", "CONGESTION",
              f"Открытых приглашений уже {c.open_invites}: карточка чуть ниже")
    tier = None
    if fit is not None and basis == "fit":
        tier = fit_tier(fit)
        if USE_FIT_TIERS:
            _note(info, reasons, "info", "FIT_TIER", f"Ярус соответствия {tier} из {tier_ceiling()}")
    confirmed = 1 if c.grade_source == "assessed" else 0
    return MatchResult(round(total, 4), factors, plus, minus, info, basis, reasons,
                       fit=None if fit is None else round(fit, 4), tier=tier, confirmed=confirmed)


def accept_probability(offer_from: int | None, offer_to: int | None,
                       want_from: int | None, want_to: int | None) -> float | None:
    """Chance the candidate accepts this gross band. None when either side named no number.

    The candidate's floor is the start of the wish. The employer's ceiling is what they can pay.
    The ceiling covering the floor is 1. A shortfall fades to 0 at 40 % under the floor.
    An offer that sits entirely above the wish is 1: more money is not a reason to refuse.
    """
    if offer_from is None and offer_to is None:
        return None
    if want_from is None and want_to is None:
        return None
    ceiling = offer_to if offer_to is not None else offer_from
    floor = want_from if want_from is not None else want_to
    if ceiling is None or floor is None or floor <= 0 or ceiling < 0:
        return None
    if ceiling >= floor:
        return 1.0
    return max(0.0, 1.0 - ((floor - ceiling) / floor) / 0.40)


def _harmonic(left: float, right: float) -> float:
    """Harmonic mean. A zero on either side is a zero: one side unwilling ends the match."""
    left = min(1.0, max(0.0, left))
    right = min(1.0, max(0.0, right))
    if left <= 0.0 or right <= 0.0:
        return 0.0
    return 2.0 * left * right / (left + right)


def pay_counterfactual(need: NeedSpec, people: list[CandidateFacts]) -> dict | None:
    """How many named wishes the current ceiling covers, and how many a 15 % higher ceiling would.

    Fewer than five named wishes is not a hint: the count would be a handful of people.
    """
    ceiling = need.salary_to if need.salary_to is not None else need.salary_from
    if ceiling is None or ceiling <= 0:
        return None
    known = [c for c in people if accept_probability(need.salary_from, ceiling, c.salary_from, c.salary_to) is not None]
    if len(known) < 5:
        return None
    covered = sum(accept_probability(need.salary_from, ceiling, c.salary_from, c.salary_to) == 1.0 for c in known)
    proposed = int(round(ceiling * 1.15 / 5000.0) * 5000)
    if proposed <= ceiling:
        proposed = ceiling + 5000
    raised = sum(accept_probability(need.salary_from, proposed, c.salary_from, c.salary_to) == 1.0 for c in known)
    return {"known": len(known), "covered": covered, "proposed_to": proposed,
            "covered_if_raised": raised, "gained": max(0, raised - covered)}


def _mean(factors: list[Factor]) -> float | None:
    active = [f for f in factors if f.value is not None]
    weight = sum(f.weight for f in active)
    if not weight:
        return None
    return sum(f.weight * f.value for f in active) / weight


def category_percentile(value: float, others: list[float]) -> int | None:
    """How many of the other people in the same category this value beats, in percent.

    `others` must not include `value` itself. Alone in the category there is no percent.
    """
    if not others:
        return None
    below = sum(1 for item in others if item < value)
    return round(100 * below / len(others))


def skill_counterfactual(need: NeedSpec, people: list[CandidateFacts]) -> dict | None:
    """The required skill that, dropped alone, would complete coverage for the most people.

    Counts only candidates who already have every other required skill. Fewer than five people,
    or a need with a single required skill, has no hint.
    """
    required = list(dict.fromkeys(need.skills))
    if len(required) < 2 or len(people) < 5:
        return None
    best_skill, best_gain = required[0], 0
    for skill in required:
        gained = sum(1 for person in people if [s for s in required if s not in person.skills] == [skill])
        if gained > best_gain:
            best_skill, best_gain = skill, gained
    if best_gain < 1:
        return None
    return {"skill": best_skill, "gained": best_gain, "pool": len(people)}


def anonymous_compare(cards: list[dict], ids: list[str]) -> list[dict]:
    """Up to four cards from the current list, without name, contacts or FSP id."""
    by_id = {c.get("candidate_id"): c for c in cards}
    rows = []
    for cid in ids[:4]:
        card = by_id.get(cid)
        if not isinstance(card, dict):
            continue
        match = card.get("match") or {}
        rows.append({
            "candidate_id": cid,
            "role": card.get("role"),
            "grade": card.get("grade"),
            "grade_source": card.get("grade_source"),
            "score": match.get("score"),
            "factors": match.get("factors") or [],
            "plus": match.get("plus") or [],
            "minus": match.get("minus") or [],
            "reasons": match.get("reasons") or [],
        })
    return rows


def recommended_categories(rows: list[tuple[str | None, str | None, float]], top: int = 3,
                           min_n: int = 5) -> list[dict]:
    """Strongest role × grade cells in this list. A cell under min_n is not recommended:
    the showcase hides that count as «<5», and a chip must not name fewer people.
    """
    cells: dict[tuple[str | None, str | None], list[float]] = {}
    for role, grade, s in rows:
        cells.setdefault((role, grade), []).append(s)
    ranked = sorted(cells.items(), key=lambda kv: (-sum(sorted(kv[1])[-5:]) / min(5, len(kv[1])), -len(kv[1])))
    ranked = [item for item in ranked if len(item[1]) >= min_n]
    return [{"role": r, "grade": g, "candidates": len(v), "best": round(max(v), 3)} for (r, g), v in ranked[:top]]
