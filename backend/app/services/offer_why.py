"""«Почему вас пригласили»: the candidate's side of the reverse mechanics.

The employer found the candidate through search, so the reasons are the same signals the search reads:
the category, whether the test confirmed the grade, the FSP history in the profile discipline and the
work format. Every line is built from the candidate's own data and the offer the candidate already sees.
Nothing about the employer's need, its weights or other candidates is shown. No new scoring: codes and
wording follow the reason codes of ``services.matching``.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.services.categorization import DISCIPLINE_LABELS
from app.services.fsp.relevance import OTHER_DISCIPLINE, lcb_for_need
from app.services.matching import GRADE_RU
from app.services.scoring.engine import LCB0
from app.services.survey import SPECIALIZATIONS

MAX_LINES = 4

# Words in a free-text offer title that name a specialization. Short tokens match whole words only.
_ROLE_WORDS: dict[str, tuple[str, ...]] = {
    "backend": ("backend", "back-end", "бэкенд", "бекенд", "бэк-енд", "серверн"),
    "frontend": ("frontend", "front-end", "фронтенд", "фронт-енд", "верстальщик"),
    "fullstack": ("fullstack", "full-stack", "full stack", "фулстек", "фуллстек"),
    "mobile": ("mobile", "android", "ios", "мобильн", "flutter", "kotlin multiplatform"),
    "ml": ("ml", "machine learning", "data scientist", "data science", "машинн", "нейросет", "ии"),
    "devops": ("devops", "sre", "девопс", "инфраструктур", "platform engineer"),
    "security": ("security", "appsec", "pentest", "пентест", "безопасност", "иб", "soc"),
    "embedded": ("embedded", "firmware", "встраива", "встроенн", "робот", "бас", "микроконтрол"),
    "qa": ("qa", "тестировщик", "тестирован", "sdet", "aqa"),
    "analyst": ("analyst", "аналитик"),
    "data": ("data engineer", "инженер данных", "dwh", "etl"),
}
# Checked first: a "Fullstack" title must not read as backend or frontend, "data engineer" not as analyst.
_ORDER = ("fullstack", "data", "ml", "devops", "security", "embedded", "mobile", "qa", "analyst", "backend", "frontend")
_FORMAT_RU = {"remote": "удалённо", "hybrid": "гибрид", "office": "в офисе"}


def _has(text: str, word: str) -> bool:
    if len(word) <= 3:
        return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None
    return word in text


def offer_role(title: str | None) -> str | None:
    """The specialization a free-text offer title names, or None when it names none or several."""
    text = (title or "").lower()
    for role in _ORDER:
        if any(_has(text, word) for word in _ROLE_WORDS[role]):
            return role
    return None


def _day(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%d.%m.%Y")


def why_invited(*, offer_title: str | None, offer_format: str | None,
                role: str | None, grade: str | None, grade_source: str | None,
                assessed_at: datetime | date | None, fsp_scores: dict[str, float],
                work_formats: list[str] | None) -> list[dict[str, str]]:
    """Up to four ``{code, text}`` lines for one offer, from the candidate's own data only."""
    lines: list[dict[str, str]] = []
    if role and grade:
        category = f"{SPECIALIZATIONS.get(role, role)} · {GRADE_RU.get(grade, grade)}"
        asked = offer_role(offer_title)
        if asked == role:
            lines.append({"code": "CATEGORY_MATCH",
                          "text": f"Ваша категория «{category}» совпадает с ролью приглашения"})
        else:
            lines.append({"code": "CATEGORY_OTHER",
                          "text": f"Ваша категория «{category}». Роль приглашения компания назвала сама"})
    if grade:
        if grade_source == "assessed":
            day = _day(assessed_at)
            tail = f" {day}" if day else ""
            lines.append({"code": "GRADE_ASSESSED",
                          "text": f"Грейд «{GRADE_RU.get(grade, grade)}» подтверждён тестом{tail}"})
        else:
            lines.append({"code": "GRADE_DECLARED",
                          "text": "Грейд не подтверждён тестом — в выдаче вы ниже тех, кто его подтвердил"})
    if fsp_scores:
        lcb, kind, discipline = lcb_for_need(role, fsp_scores)
        label = DISCIPLINE_LABELS.get(discipline or "", discipline or "")
        if lcb <= LCB0:
            # At or below the prior floor the FSP axis adds nothing to the score (matching.fsp_factor).
            lines.append({"code": "FSP_NO_LIFT", "text": "Результаты ФСП учтены, место не опускают"})
        elif kind == "other":
            weight = f"{OTHER_DISCIPLINE:.1f}".replace(".", ",")
            lines.append({"code": "FSP_OTHER",
                          "text": f"Результаты ФСП в другой дисциплине ({label}) учтены с весом {weight}"})
        elif kind == "profile":
            lines.append({"code": "FSP_RELEVANT",
                          "text": f"Результат ФСП в профильной дисциплине: {label}"})
        else:
            lines.append({"code": "FSP_SCORE", "text": f"Результаты ФСП учтены: {label}"})
    else:
        lines.append({"code": "FSP_NEUTRAL",
                      "text": "Без истории ФСП — эта ось не учитывается и не снижает вашу позицию"})
    formats = list(work_formats or [])
    if offer_format and formats:
        shown = _FORMAT_RU.get(offer_format, offer_format)
        if offer_format in formats:
            lines.append({"code": "FORMAT_MATCH", "text": f"Формат работы «{shown}» — из выбранных вами"})
        else:
            lines.append({"code": "FORMAT_OTHER",
                          "text": f"Формат «{shown}» не из выбранных вами — "
                                  "можно отклонить с причиной «Формат работы»"})
    return lines[:MAX_LINES]
