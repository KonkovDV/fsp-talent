"""A certificate PDF is a quote for a skill. It never sets a grade.

The file has to name a known certificate. Each skill is kept only with the words
that actually appear in the file.
"""
from __future__ import annotations

from app.services.skills import extract_skills, is_grounded

_MARKERS = ("кит", "i.moscow", "компетенц")


def certificate_skills(text: str) -> list[tuple[str, str]] | None:
    folded = text.casefold()
    if not any(marker in folded for marker in _MARKERS):
        return None
    found = []
    for item in extract_skills(text):
        if is_grounded(item.evidence, text):
            found.append((item.skill, item.evidence))
    return found
