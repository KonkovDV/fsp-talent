"""A certificate PDF is a quote for a skill. It never sets a grade and never confirms a skill.

AUD-02: the file is the candidate's own, so a skill from it stays self-declared (with the quote);
only a test confirms.

The file has to name a known certificate. Each skill is kept only with the words
that actually appear in the file.
"""
from __future__ import annotations

import re

from app.services.skills import extract_skills, is_grounded

# Whole words only (AUD-02): «кит» inside «Никита» or «китайский» is not a certificate.
_MARKERS = re.compile(r"(?<!\w)(кит|i\.moscow|компетенци\w*)(?!\w)", re.IGNORECASE)


def is_pdf(raw: bytes) -> bool:
    return raw[:1024].lstrip().startswith(b"%PDF-")


def certificate_skills(text: str) -> list[tuple[str, str]] | None:
    if not _MARKERS.search(text):
        return None
    found = []
    for item in extract_skills(text):
        if is_grounded(item.evidence, text):
            found.append((item.skill, item.evidence))
    return found
