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
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.services.categorization import DISCIPLINE_LABELS
from app.services.grade_posterior import expected_rel, mass_assessed, mass_declared
from app.services.scoring.engine import LCB0
from app.services.survey import SPECIALIZATIONS

GRADES = ("intern", "junior", "middle", "senior", "lead")
GRADE_RU = {"intern": "стажёр", "junior": "джуниор", "middle": "мидл", "senior": "сеньор", "lead": "лид"}

# Fit to the need (skills, grade, role) decides who belongs in the list. Evidence (test and FSP) decides
# the order inside the category: it is added with EVIDENCE_WEIGHT, scaled by how close the candidate is to the
# requested role and grade, so a strong profile from another category is not pulled over a matching one,
# while inside the category a passed test and FSP results outrank one more self-described skill (TZ section 2).
# A missing FSP history is omitted, not scored as zero. docs/VALIDATION_MATCHING.md has the ablations.
FIT_KEYS = ("skills", "grade", "role", "text", "industry", "conditions")
EVIDENCE_KEYS = ("test", "fsp")
WEIGHTS = {
    "skills": 0.50,
    "grade": 0.20,
    "role": 0.20,
    "text": 0.05,
    "industry": 0.05,
    # City and format together, five hundredths of the fit. Omitted when the need names neither.
    "conditions": 0.05,
    "test": 0.50,
    "fsp": 0.50,
}
UNTESTED = 0.20
# A passed grade must not sit under an unchecked one. Holdout 4001–4005: Δ nDCG 0, Δ Spearman 0.
PASS_TEST_FLOOR = True
PASS_FLOOR = UNTESTED + 0.05
# Weight of the evidence next to the fit (fit has weight 1).
EVIDENCE_WEIGHT = 0.40
# Width of one fit tier, used only while USE_FIT_TIERS is on.
# Sweep on 07.10.2026, seeds 2026–2028, 800 candidates and 80 needs:
# `python -m app.validation.matching --tier-delta 0.02,0.03,0.05,0.08,0.10`
# No width keeps nDCG(full) within 0.005 of nDCG(no evidence).
# At 0.02 Spearman falls to 0.097 and overclaim rises to 24.4 %.
# The product order does not use tiers.
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
    "conditions": "Город и формат",
}
# confirmed / quoted / declared. A skill with no row is "no data" and scores 0.
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


def grade_matches(candidate_grade: str | None, need_grade: str | None, mode: str = "plus_minus") -> bool:
    """Whether a grade passes the vacancy or need filter. The match score is not this check.

    plus_minus is one step on the ladder. exact is the same grade. any does not filter.
    """
    if not need_grade or mode == "any":
        return True
    if candidate_grade not in GRADES or need_grade not in GRADES:
        return False
    if mode == "exact":
        return candidate_grade == need_grade
    return abs(GRADES.index(candidate_grade) - GRADES.index(need_grade)) <= 1


def category_pairs(role: str, grade: str, span: str = "near") -> list[tuple[str, str]] | None:
    """Who stays in a filtered search. any and wide drop the grade filter. exact is one pair.

    plus_minus is the same specialization, one grade step. near also keeps a neighbour role.
    The score is unchanged.
    """
    if span in ("any", "wide"):
        return None
    if span == "exact":
        return [(role, grade)]
    if span == "plus_minus":
        if grade not in GRADES:
            return [(role, grade)]
        index = GRADES.index(grade)
        pairs = [(role, grade)]
        if index > 0:
            pairs.append((role, GRADES[index - 1]))
        if index + 1 < len(GRADES):
            pairs.append((role, GRADES[index + 1]))
        return pairs
    return near_pairs(role, grade)


def near_pairs(role: str, grade: str) -> list[tuple[str, str]]:
    """The asked category, one grade step on the same role, and a neighbour role at the same grade.

    Two steps away stay out. The score still explains a neighbour and sorts the exact pair first.
    """
    if grade not in GRADES:
        return [(role, grade)]
    index = GRADES.index(grade)
    pairs = [(role, grade)]
    if index > 0:
        pairs.append((role, GRADES[index - 1]))
    if index + 1 < len(GRADES):
        pairs.append((role, GRADES[index + 1]))
    for neighbour in sorted(ROLE_NEIGHBOURS.get(role, ())):
        pairs.append((neighbour, grade))
    return pairs


def freshness_of(tested_at: datetime | None, now: datetime | None = None) -> tuple[float, str | None]:
    """Full credit for half a year, 0.85 until a year, 0.70 after. No date leaves the factor alone."""
    if tested_at is None:
        return 1.0, None
    moment = tested_at if tested_at.tzinfo else tested_at.replace(tzinfo=UTC)
    age = (now or datetime.now(UTC)) - moment
    if age <= timedelta(days=180):
        return 1.0, "Тест не старше полугода"
    if age <= timedelta(days=365):
        return 0.85, "Тесту больше полугода: вклад теста ×0,85"
    return 0.70, "Тесту больше года: вклад теста ×0,70"


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
# "boost" (shipped since the 2026-10 audit): a history can only raise the evidence above the test,
# so taking part in FSP competitions never moves a candidate down. "mean" is the old average of the
# two factors: a weak FSP line pulled a good test down. Kept only so the holdout prints before/after.
FSP_LIFT = "boost"
FSP_OMEGA = WEIGHTS["fsp"] / (WEIGHTS["test"] + WEIGHTS["fsp"])
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
    "VERIFIED_SKILL": "тест", "TEST_SCORE": "тест", "TEST_FRESH": "тест", "UNTESTED": "тест",
    "FSP_BONUS": "ФСП", "FSP_SCORE": "ФСП", "FSP_NEUTRAL": "ФСП", "FSP_NO_LIFT": "ФСП",
    "FSP_RELEVANT": "ФСП", "FSP_OTHER": "ФСП",
    "GRADE_DECLARED": "заявлено", "GRADE_TEST_FAILED": "тест", "SKILL_COVERAGE": "заявлено", "SKILL_GAP": "заявлено",
    "SKILL_UNTESTED": "заявлено", "SKILL_NOT_PASSED": "тест",
    "RELATED_SKILL": "заявлено",
    "PAY_FIT": "вилка", "PAY_LOW": "вилка", "PAY_GAP": "вилка", "SALARY_HISTORY": "вилка",
    "CONGESTION": "очередь",
    "JOB_SEARCH_ACTIVE": "профиль", "JOB_SEARCH_OPEN": "профиль",
    "PLACE_MATCH": "город", "PLACE_OTHER": "город", "PLACE_OPEN": "город",
    "FORMAT_MATCH": "формат", "FORMAT_PART": "формат", "FORMAT_OTHER": "формат",
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
    city: str | None = None               # from the directory; omitted from the score when empty
    work_format: str | None = None        # office | hybrid | remote


@dataclass
class CandidateFacts:
    role: str | None
    grade: str | None
    grade_source: str | None              # assessed | declared | experience | default
    skills: dict[str, str] = field(default_factory=dict)   # name -> trust level
    test_p: float | None = None           # P(level) of the confirmation for this specialization
    test_spec: str | None = None
    fsp_lcb: float | None = None          # None: no FSP history
    fsp_kind: str | None = None           # profile | other | None (plain line, or no history)
    fsp_discipline: str | None = None     # discipline code behind fsp_lcb, for the card line
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
    city: str | None = None
    work_formats: tuple[str, ...] = ()
    p_up: float | None = None             # P(θ ≥ cut of the next grade); used only by GRADE_MODEL=expected
    fail_rate: float | None = None        # π for a declared grade; None keeps the legacy 0.85 factor
    tested_at: datetime | None = None     # confirmation date; None leaves the test factor unchanged
    # Target of the latest grade test in this specialization that was not passed (outcome "not_passed").
    # Only read while the shown grade is not confirmed; see grade_for_matching.
    failed_grade: str | None = None
    # Profile skills a finished test had items on (F24b). Read only by the explanation, never by the score.
    tested_skills: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Factor:
    key: str
    label: str
    weight: float
    value: float | None                   # None: not applicable
    contrib: float | None = None          # share of the employer score; the bars sum to it


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
    employer: float = 0.0             # sum of the bar contributions, before the pay match and the queue
    accept: float | None = None       # pay-band match, after refusals and the job-search factor
    congestion: float = 0.0           # points taken off for a busy invitation queue
    # Geometric mutual fit. Shown beside the score. It does not replace the score or the FSP axis.
    mutual: float | None = None
    rejected_by: list[str] = field(default_factory=list)


def reason_source(code: str) -> str | None:
    return REASON_SOURCE.get(code)


def fit_tier(fit: float, delta: float | None = None) -> int:
    """Band of a fit score in [0, 1] (TZ 2.1). A hair above the cut stays in the upper band."""
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


EVIDENCE_REASONS = {"test": ("TEST_SCORE", "UNTESTED"),
                    "fsp": ("FSP_BONUS", "FSP_SCORE", "FSP_RELEVANT", "FSP_OTHER", "FSP_NO_LIFT")}


def fsp_factor(lcb: float) -> float:
    """0 at the empty-history bound, 1 at a full result. Below the empty bound stays 0."""
    span = FSP_FULL_LCB - LCB0
    return min(1.0, max(0.0, (lcb - LCB0) / span))


def combine_evidence(test: float | None, fsp: float | None) -> float | None:
    """FSP adds only the part above the test. No history leaves the test as it is."""
    if test is None and fsp is None:
        return None
    if test is None:
        return fsp
    if fsp is None or fsp <= test:
        return test
    return test + FSP_OMEGA * (fsp - test)


def _evidence_parts(test: float | None, fsp: float | None) -> dict[str, float]:
    """How much of the evidence number comes from the test and how much from FSP."""
    if FSP_LIFT != "boost":
        present = {k: v for k, v in (("test", test), ("fsp", fsp)) if v is not None}
        weight = sum(WEIGHTS[k] for k in present)
        if not weight:
            return {}
        return {k: WEIGHTS[k] / weight * v for k, v in present.items()}
    if test is None and fsp is None:
        return {}
    if test is None:
        return {"fsp": fsp}
    if fsp is None or fsp <= test:
        return {"test": test}
    return {"test": test, "fsp": FSP_OMEGA * (fsp - test)}


def _contributions(factors: list[Factor], evidence: float | None, closeness: float,
                   basis: str) -> list[Factor]:
    """Each bar's share of the employer score. Present factors sum to that score."""
    lam = EVIDENCE_WEIGHT
    fit_rows = [f for f in factors if f.key in FIT_KEYS and f.value is not None]
    ev_rows = [f for f in factors if f.key in EVIDENCE_KEYS and f.value is not None]
    w_fit = sum(f.weight for f in fit_rows)
    w_ev = sum(f.weight for f in ev_rows)
    parts = None
    if FSP_LIFT == "boost":
        by_key = {f.key: f.value for f in ev_rows}
        parts = _evidence_parts(by_key.get("test"), by_key.get("fsp"))
    out = []
    for f in factors:
        share = None
        if f.value is None:
            out.append(f)
            continue
        if parts is not None and f.key in EVIDENCE_KEYS:
            # Boost: the evidence is test + ω·(fsp − test)⁺, so each bar carries its own part of it.
            part = parts.get(f.key, 0.0)
            if basis == "evidence":
                share = part
            elif evidence is not None:
                share = lam * closeness * part / (1.0 + lam)
            out.append(replace(f, contrib=share))
            continue
        if basis == "evidence":
            if f.key in EVIDENCE_KEYS and w_ev:
                share = f.weight * f.value / w_ev
        elif f.key in FIT_KEYS and w_fit:
            share = f.weight * f.value / w_fit / (1.0 + lam)
        elif f.key in EVIDENCE_KEYS and w_ev and evidence is not None:
            share = lam * closeness * (f.weight * f.value / w_ev) / (1.0 + lam)
        out.append(replace(f, contrib=share))
    return out


def _with_points(reasons: list[Reason], factors: list[Factor], scale: float) -> list[Reason]:
    """Attach to the test and FSP lines how much each moved the score, so the card shows the contribution."""
    by_key = {f.key: f.value for f in factors if f.key in EVIDENCE_KEYS}
    parts = _evidence_parts(by_key.get("test"), by_key.get("fsp"))
    if not parts:
        return reasons
    points = {k: scale * v for k, v in parts.items() if v}
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


def conditions_value(need: NeedSpec, c: CandidateFacts) -> float | None:
    """City and format as one factor. An unnamed side is not a penalty. A mismatch is not a ban."""
    parts: list[float] = []
    if need.city:
        if not c.city or c.city.casefold() == need.city.casefold():
            parts.append(1.0)
        else:
            parts.append(0.0)
    if need.work_format:
        have = tuple(c.work_formats or ())
        if not have or need.work_format in have:
            parts.append(1.0)
        elif "hybrid" in have or need.work_format == "hybrid":
            parts.append(0.6)
        else:
            parts.append(0.0)
    if not parts:
        return None
    return sum(parts) / len(parts)


def grade_for_matching(grade: str | None, source: str | None, failed_grade: str | None) -> tuple[str | None, bool]:
    """The grade the need-fit reads, and whether a failed test lowered it.

    A test at grade G that was not passed is evidence that the ability is below the cut of G
    (P(θ ≥ cut_G) < PASS_P, app/services/cat.py). While the candidate keeps an unconfirmed grade
    G' ≥ G, matching reads the grade one step below the failed target. The card still shows the
    grade the candidate chose, marked as not confirmed (Q&A FTT.4): the person is lowered, not hidden.
    A confirmed grade is never touched, and neither is a failed test above the shown grade
    (a declined attempt at the next step says nothing against the current one).
    """
    if source == "assessed" or grade not in GRADES or failed_grade not in GRADES:
        return grade, False
    target = GRADES.index(failed_grade)
    if target > GRADES.index(grade):
        return grade, False
    return GRADES[max(target - 1, 0)], True


def score(need: NeedSpec, c: CandidateFacts, use_trust: bool = True, use_test: bool = True,
          use_fsp: bool = True, use_related: bool = True) -> MatchResult:
    """Factor score with plus / minus / info lines (TZ 2.1). The use_* switches exist for the ablation study."""
    values: dict[str, float | None] = {k: None for k in WEIGHTS}
    plus: list[str] = []
    minus: list[str] = []
    info: list[str] = []
    reasons: list[Reason] = []

    wanted = [(s, 1.0) for s in need.skills] + [(s, 0.5) for s in need.nice if s not in need.skills]
    if wanted:
        total = got = 0.0
        confirmed, related, missing, untested, not_passed = [], [], [], [], []
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
            elif how != "missing" and not how.startswith("related"):
                # In the profile, but no test confirmed it. Not the same as a missing skill (SKILL_GAP).
                # F24b: a finished test with items on it is "checked, not confirmed"; otherwise never checked.
                (not_passed if skill in c.tested_skills else untested).append(skill)
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
        # F24/F24b: only the explanation changes; the credit above already weighs these by TRUST.
        if not_passed:
            _note(info, reasons, "info", "SKILL_NOT_PASSED",
                  "Проверены тестом, не подтверждены: " + ", ".join(not_passed))
        if untested:
            _note(info, reasons, "info", "SKILL_UNTESTED",
                  "Заявлены, тестом не проверялись: " + ", ".join(untested))
        if related:
            _note(info, reasons, "info", "RELATED_SKILL",
                  "Близкие технологии (частичный зачёт): " + ", ".join(related))
        if missing:
            _note(minus, reasons, "minus", "SKILL_GAP", "Нет навыков: " + ", ".join(missing))

    closeness = 1.0   # 1 inside the requested category; evidence weighs less the further the candidate is from it
    # The failed-test step is test evidence, so the ablation without the test does not see it either.
    grade, failed = (grade_for_matching(c.grade, c.grade_source, c.failed_grade) if use_test
                     else (c.grade, False))
    if need.grade in GRADES and grade in GRADES:
        gap = GRADES.index(grade) - GRADES.index(need.grade)
        base = {0: 1.0, 1: 0.6, -1: 0.35}.get(gap, 0.0)
        assessed = c.grade_source == "assessed"
        expected = settings.GRADE_MODEL == "expected" and use_test and (assessed or c.fail_rate is not None)
        if expected and assessed:
            belief = mass_assessed(grade, c.test_p if c.test_p is not None else 1.0, c.p_up or 0.0)
            grade_value = expected_rel(need.grade, belief)
        elif expected and c.fail_rate is not None:
            belief = mass_declared(grade, c.fail_rate)
            grade_value = expected_rel(need.grade, belief)
        else:
            grade_value = base * (1.0 if assessed or not use_test else DECLARED_GRADE)
        closeness *= grade_value if expected else base
        values["grade"] = grade_value
        if failed:
            _note(minus, reasons, "minus", "GRADE_TEST_FAILED",
                  f"Грейд «{GRADE_RU[c.grade]}» тестом не подтверждён: тест на «{GRADE_RU[c.failed_grade]}» "
                  f"не пройден, в подборе учтён «{GRADE_RU[grade]}»")
        if gap == 0:
            if failed:
                pass   # the line above already names the grade that entered the score
            elif expected and not assessed and c.fail_rate is not None:
                passed = round((1.0 - c.fail_rate) * 100)
                text = (f"Грейд заявлен; тест на этот грейд с первого раза сдают {passed} % "
                        f"— вклад грейда ×{1.0 - c.fail_rate:.2f}")
                _note(info, reasons, "info", "GRADE_DECLARED", text)
            else:
                tail = " подтверждён тестом" if assessed else " указан кандидатом, тестом не подтверждён"
                text = f"Грейд «{GRADE_RU[grade]}»{tail}"
                if assessed:
                    _note(plus, reasons, "plus", "CATEGORY_MATCH", text)
                else:
                    _note(info, reasons, "info", "GRADE_DECLARED", text)
        elif gap > 0:
            _note(info, reasons, "info", "GRADE_ABOVE", f"Грейд выше запрошенного: {GRADE_RU[grade]}")
        else:
            _note(minus, reasons, "minus", "GRADE_BELOW", f"Грейд ниже запрошенного: {GRADE_RU[grade]}")
    elif failed:
        _note(minus, reasons, "minus", "GRADE_TEST_FAILED",
              f"Грейд «{GRADE_RU[c.grade]}» тестом не подтверждён: тест на «{GRADE_RU[c.failed_grade]}» не пройден")

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
            if (PASS_TEST_FLOOR and c.grade_source == "assessed" and need.grade
                    and c.grade == need.grade):
                shown = max(shown, PASS_FLOOR)
            if shown != c.test_p:
                _note(plus, reasons, "plus", "TEST_SCORE",
                      f"Тест: нижняя граница уровня {round(shown * 100)} % "
                      f"(точечная оценка {round(c.test_p * 100)} %)")
            else:
                _note(plus, reasons, "plus", "TEST_SCORE", f"Тест: вероятность уровня {round(c.test_p * 100)}%")
            # A passed test never scores below "not tested". The lower bound at the pass mark
            # (Φ(Φ⁻¹(0.75) − 1.64) ≈ 0.17) fell under UNTESTED = 0.20; age now shrinks only the part above it.
            shown = max(UNTESTED, shown)
            values["test"] = shown
            factor, fresh = freshness_of(c.tested_at)
            if factor != 1.0:
                values["test"] = round(UNTESTED + (shown - UNTESTED) * factor, 4)
            if fresh:
                _note(info, reasons, "info", "TEST_FRESH", fresh)
        else:
            values["test"] = UNTESTED
            if not failed and not any("тестом не подтверждён" in line for line in info):
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
            if FSP_LIFT == "boost":
                values["fsp"] = fsp_factor(c.fsp_lcb)
            else:
                values["fsp"] = min(1.0, max(0.0, c.fsp_lcb / FSP_FULL_LCB))
            no_lift = FSP_LIFT == "boost" and values["test"] is not None and values["fsp"] <= values["test"]
            if no_lift:
                _note(info, reasons, "info", "FSP_NO_LIFT", "Результаты ФСП учтены, место не опускают")
            elif c.fsp_kind == "profile":
                label = DISCIPLINE_LABELS.get(c.fsp_discipline or "", c.fsp_discipline or "")
                tone, bucket = ("plus", plus) if values["fsp"] >= 0.5 else ("info", info)
                _note(bucket, reasons, tone, "FSP_RELEVANT", f"Результат в профильной дисциплине: {label}")
            elif c.fsp_kind == "other":
                _note(info, reasons, "info", "FSP_OTHER",
                      "Результаты ФСП в другой дисциплине учтены с весом 0,5")
            elif values["fsp"] >= 0.5:
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

    cond = conditions_value(need, c)
    if cond is not None:
        values["conditions"] = cond
        if need.city:
            if not c.city:
                _note(info, reasons, "info", "PLACE_OPEN", "Город не указан и не штрафуется")
            elif c.city.casefold() == need.city.casefold():
                _note(plus, reasons, "plus", "PLACE_MATCH", f"Город совпадает: {need.city}")
            else:
                _note(minus, reasons, "minus", "PLACE_OTHER", f"Другой город: {c.city}")
        if need.work_format:
            have = tuple(c.work_formats or ())
            if have and need.work_format in have:
                _note(plus, reasons, "plus", "FORMAT_MATCH", "Формат работы подходит")
            elif have and ("hybrid" in have or need.work_format == "hybrid"):
                _note(info, reasons, "info", "FORMAT_PART", "Формат работы совпадает частично")
            elif have:
                _note(minus, reasons, "minus", "FORMAT_OTHER", "Формат работы не совпадает")

    bare = [Factor(k, LABELS[k], WEIGHTS[k], values[k]) for k in (*FIT_KEYS, *EVIDENCE_KEYS)]
    fit = _mean([f for f in bare if f.key in FIT_KEYS])
    if FSP_LIFT == "boost":
        evidence = combine_evidence(values["test"], values["fsp"])
    else:
        evidence = _mean([f for f in bare if f.key in EVIDENCE_KEYS])
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
        reasons = _with_points(reasons, bare, EVIDENCE_WEIGHT * closeness / (1.0 + EVIDENCE_WEIGHT))
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
    factors = _contributions(bare, evidence, closeness, basis)
    congestion = 0.0
    total = employer
    if accept is not None:
        # Reciprocal score: harmonic mean of "the employer would invite" and "the candidate would accept".
        # Absent on either side, the factor is omitted and the ranking stays the employer-only score.
        total = _harmonic(employer, accept)
    if c.open_invites > OPEN_INVITE_FREE:
        congestion = min(CONGESTION_CAP, CONGESTION_STEP * (c.open_invites - OPEN_INVITE_FREE))
        total = max(0.0, total - congestion)
        _note(info, reasons, "info", "CONGESTION",
              f"Открытых приглашений уже {c.open_invites}: карточка чуть ниже")
    tier = None
    if fit is not None and basis == "fit":
        tier = fit_tier(fit)
        if USE_FIT_TIERS:
            _note(info, reasons, "info", "FIT_TIER", f"Ярус соответствия {tier} из {tier_ceiling()}")
    confirmed = 1 if c.grade_source == "assessed" else 0
    qualification = fit if fit is not None else employer
    opportunity, blocked = _opportunity(need, c, accept)
    mutual = mutual_fit(qualification, opportunity, _intent(c.job_search))
    return MatchResult(round(total, 4), factors, plus, minus, info, basis, reasons,
                       fit=None if fit is None else round(fit, 4), tier=tier, confirmed=confirmed,
                       employer=employer, accept=accept, congestion=congestion,
                       mutual=mutual, rejected_by=blocked)


Q_POWER, O_POWER, I_POWER = 0.55, 0.30, 0.15


def mutual_fit(qualification: float, opportunity: float, intent: float) -> float:
    """Qualification × opportunity × intent. A zero opportunity is a zero: skills do not rescue it.

    The powers sum to 1. This number is not the list order and does not read the FSP lower bound.
    """
    q = min(1.0, max(0.0, qualification))
    o = min(1.0, max(0.0, opportunity))
    i = min(1.0, max(0.0, intent))
    return round((q ** Q_POWER) * (o ** O_POWER) * (i ** I_POWER), 4)


def _intent(job_search: str | None) -> float:
    return {"active": 1.0, "open": 0.75}.get(job_search or "open", 0.35)


def _opportunity(need: NeedSpec, person: CandidateFacts, accept: float | None) -> tuple[float, list[str]]:
    """Pay and format. An unnamed side is not a block. A hard miss zeroes the opportunity."""
    parts: list[float] = []
    blocked: list[str] = []
    if accept is not None:
        parts.append(accept)
        if accept < 0.5:
            blocked.append("salary")
    if need.work_format:
        have = tuple(person.work_formats or ())
        if not have or need.work_format in have:
            parts.append(1.0)
        elif "hybrid" in have or need.work_format == "hybrid":
            parts.append(0.6)
        else:
            parts.append(0.0)
            blocked.append("format")
    if not parts:
        return 1.0, blocked
    if any(part == 0.0 for part in parts):
        return 0.0, blocked
    return sum(parts) / len(parts), blocked


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


def reply_outlook(need: NeedSpec, person: CandidateFacts) -> dict | None:
    """Chance they answer this need. Shown before the invite. Not an input of the score.

    A named salary on both sides is required: without it the figure would be a guess, and the
    list order must not move when the figure appears. Format and city enter only when the need
    names them. A city the candidate left blank is not a penalty. Looking now counts more than
    "will consider".
    """
    pay = accept_probability(need.salary_from, need.salary_to, person.salary_from, person.salary_to)
    if pay is None:
        return None
    z = -0.15 + 1.8 * (pay - 0.5)
    if need.work_format:
        have = tuple(person.work_formats or ())
        if not have or need.work_format in have:
            fmt = 1.0
        elif "hybrid" in have or need.work_format == "hybrid":
            fmt = 0.6
        else:
            fmt = 0.0
        z += 0.9 * (fmt - 0.5)
    if need.city and (person.city or "").strip():
        same = person.city.strip().casefold() == need.city.strip().casefold()
        z += 0.6 * ((1.0 if same else 0.0) - 0.5)
    activity = {"active": 1.0, "open": 0.55}.get(person.job_search, 0.2)
    z += 0.8 * (activity - 0.5)
    p = round(min(0.99, max(0.01, 1.0 / (1.0 + math.exp(-z)))), 3)
    label = "высокая" if p >= 0.7 else "средняя" if p >= 0.4 else "низкая"
    return {"p": p, "label": label}


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


def standing_line(pct: int, label: str) -> str:
    """Short place in the category. The percent is how many others this result beats."""
    if pct > 50:
        word = "Выше среднего"
    elif pct < 50:
        word = "Ниже среднего"
    else:
        word = "На среднем уровне"
    return f"{word} по категории {label}: лучше {pct} %"


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
