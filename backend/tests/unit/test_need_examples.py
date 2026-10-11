"""M1: the three one-click need examples parse into a usable draft, and README quotes the same lines."""
import re
from pathlib import Path

import pytest

from app.services.need_draft import draft_need

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = re.findall(r"text: '([^']+)'", (ROOT / "frontend/src/needExamples.ts").read_text(encoding="utf-8"))


def test_there_are_three_examples_and_readme_quotes_them():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(EXAMPLES) == 3
    for text in EXAMPLES:
        assert f"«{text}»" in readme


@pytest.mark.parametrize("text", EXAMPLES)
def test_each_example_gives_a_role_a_grade_and_three_skills(text):
    draft = draft_need(text)
    assert draft["role"] and draft["grade"]
    assert len(draft["skills"]) >= 3
