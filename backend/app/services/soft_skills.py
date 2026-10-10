"""Soft skills a candidate can put on the card. They are not part of the match score.

The same names are what the resume parser may quote. A name outside the list is refused.
"""
from __future__ import annotations

ITEMS = (
    ("Коммуникация", ("коммуникац", "коммуникабельн")),
    ("Командная работа", ("командн", "в команде")),
    ("Наставничество", ("наставни", "ментор")),
    ("Лидерство", ("лидерств",)),
    ("Публичные выступления", ("презентац", "выступлен")),
)
NAMES = tuple(name for name, _ in ITEMS)
_MAX = 5


def clean(names: list[str]) -> list[str]:
    out: list[str] = []
    for name in names:
        if name in NAMES and name not in out:
            out.append(name)
    if len(out) > _MAX:
        raise ValueError(f"Не больше {_MAX}")
    return out
