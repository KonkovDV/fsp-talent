"""A review mark when two practice solutions share most of their fingerprints.

Winnowing keeps the smallest hash in each window, the same selection MOSS uses.
Grams of the shared function header are removed before the comparison, so the
template does not count as a shared solution. The mark does not change the
check result and is not a finding of copying. Names, strings and numbers are
collapsed so a rename does not hide a shared shape.
"""
from __future__ import annotations

import hashlib
import re

THRESHOLD = 0.85
MIN_TOKENS = 30
GRAM = 5
WINDOW = 4

# Every practice solution starts with this header. Its grams are not evidence.
TEMPLATE = "def solve(xs):\n    return 0\n"

_TOKEN = re.compile(
    r"#[^\n]*|'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|'[^'\n]*'|\"[^\"\n]*\"|\d+|[_A-Za-z][_A-Za-z0-9]*|\S"
)


def tokenize(source: str) -> list[str]:
    out: list[str] = []
    for raw in _TOKEN.findall(source):
        if raw.startswith("#"):
            continue
        if raw.startswith(("'", '"')):
            out.append("STR")
        elif raw.isdigit():
            out.append("NUM")
        elif raw[0].isalpha() or raw[0] == "_":
            out.append("ID")
        elif raw.strip():
            out.append(raw)
    return out


def fingerprints(tokens: list[str]) -> set[str]:
    if len(tokens) < GRAM:
        return set()
    grams = [hashlib.sha256(" ".join(tokens[i:i + GRAM]).encode()).hexdigest()
             for i in range(len(tokens) - GRAM + 1)]
    picked: set[str] = set()
    for start in range(0, len(grams) - WINDOW + 1):
        window = grams[start:start + WINDOW]
        picked.add(min(window))
    if len(grams) < WINDOW:
        picked.add(min(grams))
    return picked


def template_grams() -> set[str]:
    return fingerprints(tokenize(TEMPLATE))


def compared(source: str) -> set[str]:
    """Fingerprints of one solution with the shared header taken out."""
    return fingerprints(tokenize(source)) - template_grams()


def similar(left: str, right: str) -> float:
    a, b = tokenize(left), tokenize(right)
    if len(a) < MIN_TOKENS or len(b) < MIN_TOKENS:
        return 0.0
    fa, fb = compared(left), compared(right)
    if not fa or not fb:
        return 0.0
    return len(fa & fb) / min(len(fa), len(fb))


def copy_mark(source: str, others: list[str]) -> bool:
    return any(similar(source, other) >= THRESHOLD for other in others)
