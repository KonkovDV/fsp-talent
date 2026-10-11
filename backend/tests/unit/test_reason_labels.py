"""Every reason code the matcher emits has a Russian label on the card (stand ST-UI-04: raw TEST_FRESH)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _emitted() -> set[str]:
    src = (ROOT / "backend/app/services/matching.py").read_text(encoding="utf-8")
    codes = set(re.findall(r'_note\(\w+, \w+, "\w+", "([A-Z_]+)"', src))
    codes |= set(re.findall(r'"(INTERVIEW_[A-Z_]+)"', src))
    return codes


def _labelled() -> set[str]:
    card = (ROOT / "frontend/src/components/CandidateCard.tsx").read_text(encoding="utf-8")
    block = card[card.index("const REASON_RU"):]
    block = block[:block.index("\n}")]
    labels = (ROOT / "frontend/src/labels.ts").read_text(encoding="utf-8")
    badge = labels[labels.index("JOB_SEARCH_BADGE"):]
    badge = badge[:badge.index("\n}")]
    return set(re.findall(r"\b([A-Z][A-Z_]+)\s*:", block + badge))


def test_every_emitted_reason_has_a_label():
    emitted = _emitted()
    assert len(emitted) > 20
    assert emitted - _labelled() == set()
