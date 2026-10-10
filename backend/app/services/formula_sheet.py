"""The match weights, shown on the demo stand and absent otherwise."""
from __future__ import annotations

from app.services.matching import EVIDENCE_WEIGHT, WEIGHTS

_LABELS = {
    "skills": "Навыки",
    "grade": "Грейд",
    "role": "Специализация",
    "text": "Запрос",
    "industry": "Предметная область",
    "conditions": "Город и формат",
    "test": "Тест",
    "fsp": "ФСП",
}


def formula_sheet(demo: bool) -> dict | None:
    if not demo:
        return None
    fit = ("skills", "grade", "role", "text", "industry", "conditions")
    evidence = ("test", "fsp")

    def row(key: str) -> dict:
        return {"key": key, "label": _LABELS[key], "weight": WEIGHTS[key]}

    return {
        "fit": [row(key) for key in fit],
        "evidence_weight": EVIDENCE_WEIGHT,
        "evidence": [row(key) for key in evidence],
        "note": "Список виден на демо-стенде. Вне демо этой страницы нет.",
    }
