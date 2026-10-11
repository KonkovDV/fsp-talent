"""Turn a pasted vacancy into need fields. Rules first, then word-similarity hints. Nothing is fetched."""
from __future__ import annotations

import re

from app.services.ai.assistant import parse_query
from app.services.cities import find_city
from app.services.skills import extract_skills
from app.services.survey import INDUSTRIES
from app.services.tfidf_need import suggest_skills
from app.services.vacancy_flags import vacancy_flags

_NICE = re.compile(r"будет плюсом|желательн\w*|nice to have|как плюс", re.IGNORECASE)
_THOUSANDS = re.compile(r"(\d{2,4})\s*(?:тыс\.?|тысяч|k\b)", re.IGNORECASE)
_MONEY = re.compile(r"(?<!\d)(\d{2,3}(?:[ \u00a0]\d{3})+|\d{5,7})(?!\d)")
# A salary range: «от 150 до 250 тыс», «150–250k», «200 000 ₽ – 280 000 ₽», «180k–240k», «от 200 тыс. до 260 тыс.».
# A unit written once after the second number («120–160 тыс.») applies to both bounds.
_NUM = r"\d{1,3}(?:[ \u00a0]\d{3})+|\d+(?:[.,]\d+)?"
_UNIT = r"тыс(?:яч\w*)?\.?|k(?![a-zа-я])|к(?![a-zа-я])|млн\.?"
_CUR = r"(?:₽|руб(?:\.|л\w*)?|р\.)"
_RANGE = re.compile(
    rf"(?<![\d.,])(?:от\s*)?(?P<a>{_NUM})\s*(?P<ua>{_UNIT})?\s*{_CUR}?\s*(?:-|–|—|до)\s*"
    rf"(?P<b>{_NUM})\s*(?P<ub>{_UNIT})?(?![\d%])",
    re.IGNORECASE,
)
_SALARY_MIN, _SALARY_MAX = 20_000, 2_000_000
# A title that names a stack names the specialization: «Go-разработчик», «Senior Java developer», «Разработчик C#».
# Languages used across several specializations (C++, Rust, Kotlin, JavaScript, TypeScript) are left out.
_STACK_ROLES = (
    ("backend", r"go|golang|java|python|php|ruby|scala|elixir|c#|\.net|node\.?js"),
    ("frontend", r"react|vue(?:\.js)?|angular|svelte"),
    ("mobile", r"flutter|dart|swift|react native"),
)
_DEVELOPER = r"разработчик\w*|программист\w*|developer|engineer|инженер\w*"
_STACK_TITLE = tuple(
    (role, re.compile(rf"(?<![\w#.])(?:{stack})(?![\w#])[\s-]*(?:{_DEVELOPER})|(?:{_DEVELOPER})\s+(?:{stack})(?![\w#])",
                      re.IGNORECASE))
    for role, stack in _STACK_ROLES
)
_FORMATS = (
    ("remote", re.compile(r"удал[её]н\w*|remote|из дома", re.IGNORECASE)),
    ("hybrid", re.compile(r"гибрид\w*|hybrid", re.IGNORECASE)),
    ("office", re.compile(r"\bофис\w*|\boffice\b", re.IGNORECASE)),
)
_INDUSTRY_STEMS = (
    ("fintech", "финтех"), ("ecommerce", "ритейл"), ("gamedev", "игр"),
    ("edtech", "образован"), ("govtech", "госсектор"), ("telecom", "телеком"),
    ("industry", "промышлен"), ("healthtech", "медицин"), ("media", "медиа"),
    ("security", "кибербез"),
)


def _scale(raw: str, unit: str | None) -> int:
    value = float(re.sub(r"[ \u00a0]", "", raw).replace(",", "."))
    unit = (unit or "").casefold()
    if unit.startswith("млн"):
        value *= 1_000_000
    elif unit:
        value *= 1000
    return int(round(value))


def salary_range(text: str) -> tuple[int, int] | None:
    """The first plausible «A–B» salary range with both bounds, or None. Gross/net words do not change the numbers."""
    for m in _RANGE.finditer(text):
        unit_a, unit_b = m.group("ua"), m.group("ub")
        low = _scale(m.group("a"), unit_a or unit_b)
        high = _scale(m.group("b"), unit_b or unit_a)
        if _SALARY_MIN <= low <= high <= _SALARY_MAX:
            return low, high
    return None


def _money(text: str) -> list[int]:
    found = [int(m.group(1)) * 1000 for m in _THOUSANDS.finditer(text)]
    for raw in _MONEY.findall(text):
        number = int(re.sub(r"\D", "", raw))
        if 20_000 <= number <= 2_000_000:
            found.append(number)
    return sorted(set(found))


def _split(text: str) -> tuple[list[str], list[str]]:
    cut = _NICE.search(text)
    if cut is None:
        names = [item.skill for item in extract_skills(text)]
        return names[:12], []
    required = [item.skill for item in extract_skills(text[:cut.start()])]
    nice = [item.skill for item in extract_skills(text[cut.end():])]
    nice = [name for name in nice if name not in required]
    return required[:12], nice[:12]


def _role(title: str, text: str) -> str | None:
    """The title decides first (its role word, then the stack it names), then the whole text."""
    by_title = parse_query(title).get("role")
    if by_title:
        return by_title
    for role, pattern in _STACK_TITLE:
        if pattern.search(title):
            return role
    return parse_query(text).get("role")


def _format(text: str) -> str | None:
    for code, pattern in _FORMATS:
        if pattern.search(text):
            return code
    return None


def _industry(text: str) -> str | None:
    low = text.casefold()
    for code, stem in _INDUSTRY_STEMS:
        if stem in low:
            return code
    for code, label in INDUSTRIES.items():
        if code != "any" and (code in low or label.casefold() in low):
            return code
    return None


def draft_need(text: str) -> dict:
    """Fields the employer can save. `notes` says what the text did not contain."""
    cleaned = text.strip()
    required, nice = _split(cleaned)
    parsed = parse_query(cleaned)
    amounts = _money(cleaned)
    bounds = salary_range(cleaned)
    if bounds is None and amounts:
        bounds = (amounts[0], amounts[-1])
    title = next((line.strip() for line in cleaned.splitlines() if line.strip()), "Потребность")
    internship = re.search(r"стаж[её]р|стажировк|практик|intern", cleaned, re.IGNORECASE) is not None
    draft = {
        "title": title[:80],
        "role": _role(title, cleaned),
        "grade": parsed.get("grade") or ("intern" if internship else None),
        "skills": required,
        "nice_to_have": nice,
        "salary_from": bounds[0] if bounds else None,
        "salary_to": bounds[1] if bounds else None,
        "work_format": _format(cleaned),
        "city": find_city(cleaned),
        "industry": _industry(cleaned),
        "work_goal": "internship" if internship else None,
    }
    notes = []
    if not draft["role"]:
        notes.append("Специализация не найдена, выберите её.")
    if not draft["skills"]:
        notes.append("Обязательные навыки не найдены.")
    if bounds is None:
        notes.append("Вилка не найдена.")
    if not draft["work_format"]:
        notes.append("Формат работы не найден.")
    if not draft["city"]:
        notes.append("Город не найден.")
    hinted = [name for name in suggest_skills(cleaned) if name not in required and name not in nice][:5]
    if hinted:
        notes.append("Похоже по словам, проверьте перед сохранением: " + ", ".join(hinted) + ".")
    draft["notes"] = notes
    draft["flags"] = vacancy_flags(draft.get("title") or "", cleaned)
    return draft
