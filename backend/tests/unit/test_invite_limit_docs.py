"""M2: the README line against mass invitations quotes the caps the code enforces."""
from pathlib import Path

from app.services.offers import DECLINE_PAUSE
from app.services.trust_level import INVITE_LIMIT

ROOT = Path(__file__).resolve().parents[3]


def test_readme_and_solution_quote_the_real_caps():
    low, high = INVITE_LIMIT[0], max(INVITE_LIMIT.values())
    for doc in ("README.md", "docs/SOLUTION.md"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert f"до {low} приглашений в сутки" in text
        assert f"до {high} (`INVITE_LIMIT`" in text
        assert f"через {DECLINE_PAUSE.days} дней" in text
