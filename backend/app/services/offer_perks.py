"""Extra conditions on an invitation. They do not change the match score."""
from __future__ import annotations

PERKS = {
    "fsp_tournaments": "Компенсация турниров ФСП",
    "health": "ДМС",
    "learning": "Обучение",
    "equipment": "Техника",
}


def clean_perks(codes: list[str]) -> list[str]:
    kept: list[str] = []
    for code in codes:
        if code in PERKS and code not in kept:
            kept.append(code)
        if len(kept) == 4:
            break
    return kept
