"""Turn a pasted vacancy into need fields. Rules first, then word-similarity hints. Nothing is fetched."""
from __future__ import annotations

import re

from app.services.ai.assistant import parse_query
from app.services.cities import CITIES
from app.services.skills import extract_skills
from app.services.survey import INDUSTRIES
from app.services.tfidf_need import suggest_skills

_NICE = re.compile(r"будет плюсом|желательн\w*|nice to have|как плюс", re.IGNORECASE)
_THOUSANDS = re.compile(r"(\d{2,4})\s*(?:тыс\.?|тысяч|k\b)", re.IGNORECASE)
_MONEY = re.compile(r"(?<!\d)(\d{2,3}(?:[ \u00a0]\d{3})+|\d{5,7})(?!\d)")
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


def _city(text: str) -> str | None:
    low = text.casefold()
    found = [name for name in CITIES if name.casefold() in low]
    return max(found, key=len) if found else None


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
    title = next((line.strip() for line in cleaned.splitlines() if line.strip()), "Потребность")
    draft = {
        "title": title[:80],
        "role": parsed.get("role"),
        "grade": parsed.get("grade"),
        "skills": required,
        "nice_to_have": nice,
        "salary_from": amounts[0] if amounts else None,
        "salary_to": amounts[-1] if len(amounts) > 1 else (amounts[0] if amounts else None),
        "work_format": _format(cleaned),
        "city": _city(cleaned),
        "industry": _industry(cleaned),
        "work_goal": "internship" if re.search(r"стаж[её]р|практик|intern", cleaned, re.IGNORECASE) else None,
    }
    notes = []
    if not draft["role"]:
        notes.append("Специализация не найдена, выберите её.")
    if not draft["skills"]:
        notes.append("Обязательные навыки не найдены.")
    if not amounts:
        notes.append("Вилка не найдена.")
    if not draft["work_format"]:
        notes.append("Формат работы не найден.")
    if not draft["city"]:
        notes.append("Город не найден.")
    hinted = [name for name in suggest_skills(cleaned) if name not in required and name not in nice][:5]
    if hinted:
        notes.append("Похоже по словам, проверьте перед сохранением: " + ", ".join(hinted) + ".")
    draft["notes"] = notes
    return draft
