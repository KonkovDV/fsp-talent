"""Claims from external audits that are wrong for this code must not reach the pitch or the docs.

docs-analysis part 3: «Wilson LCB» (the axis is empirical-Bayes shrinkage with LCB = μ − σ),
«test-retest ≥ 0,80» (grade agreement on a retest is κ = 0,47), «AUC ≥ 0,88» (an unmeasured threshold;
the measured adjacent-grade AUC is in VALIDATION_ASSESSMENT),
«the reranker needs a GPU» (bge-reranker-v2-m3 runs on CPU), P×L×D×C and the status-weighted
formula (all competitions weigh the same), and subjective scores (88/100, 97 %).
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FILES = ["README.md", "docs/SOLUTION.md", "docs/INSTALL.md", "docs/pitch.html", "docs/tools/build_pitch.mjs"]
FORBIDDEN = [
    r"[Ww]ilson",
    r"(retest|ретест|повторн\w+ сдач\w*)[^.\n]{0,40}≥\s*0[,.]8",
    r"\bAUC\s*≥\s*0[,.]88",
    r"(требует|нужн\w*|необходим\w*)[^.\n]{0,30}\bGPU\b",
    r"P\s*[×x]\s*L\s*[×x]\s*D\s*[×x]\s*C",
    r"\b88\s*/\s*100\b",
    r"\b97\s*%",
]


@pytest.mark.parametrize("name", FILES)
def test_no_wrong_external_claims(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    hits = [p for p in FORBIDDEN if re.search(p, text)]
    assert hits == [], f"{name}: {hits}"


def test_pitch_source_carries_the_current_numbers():
    source = (ROOT / "docs/tools/build_pitch.mjs").read_text(encoding="utf-8")
    for stale in ("0,707", "'0,01 → 0,54'", "0,650 против", "65,1 %", "из 124 запросов", "Шифрование контактов в базе"):
        assert stale not in source, stale
    assert "0,752" in source and "0,669" in source
