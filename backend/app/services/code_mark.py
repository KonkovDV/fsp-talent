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
TEMPLATES = {"python": TEMPLATE, "javascript": "function solve(xs) {\n  return 0\n}\n"}

_TOKEN = re.compile(
    r"#[^\n]*|'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|'[^'\n]*'|\"[^\"\n]*\"|\d+|[_A-Za-z][_A-Za-z0-9]*|\S"
)
# In Python // is floor division, so the comment forms differ by language.
_JS_TOKEN = re.compile(
    r"//[^\n]*|/\*[\s\S]*?\*/|`[^`]*`|'[^'\n]*'|\"[^\"\n]*\"|\d+|[_$A-Za-z][_$A-Za-z0-9]*|\S"
)
_JS_HEADER = re.compile(r"^\s*(?:function\s+solve\b|(?:const|let|var)\s+solve\s*=)", re.M)


def source_language(source: str) -> str:
    """The language a stored solution was written in. Only solutions in one language are compared."""
    return "javascript" if _JS_HEADER.search(source) else "python"


def tokenize(source: str, language: str = "python") -> list[str]:
    out: list[str] = []
    js = language == "javascript"
    pattern, comment = (_JS_TOKEN, ("//", "/*")) if js else (_TOKEN, ("#",))
    for raw in pattern.findall(source):
        if raw.startswith(comment):
            continue
        if raw.startswith(("'", '"', "`")):
            out.append("STR")
        elif raw.isdigit():
            out.append("NUM")
        elif raw[0].isalpha() or raw[0] in "_$":
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


def template_grams(language: str = "python") -> set[str]:
    return fingerprints(tokenize(TEMPLATES.get(language, TEMPLATE), language))


def compared(source: str, language: str = "python") -> set[str]:
    """Fingerprints of one solution with the shared header taken out."""
    return fingerprints(tokenize(source, language)) - template_grams(language)


def similar(left: str, right: str, language: str = "python") -> float:
    a, b = tokenize(left, language), tokenize(right, language)
    if len(a) < MIN_TOKENS or len(b) < MIN_TOKENS:
        return 0.0
    fa, fb = compared(left, language), compared(right, language)
    if not fa or not fb:
        return 0.0
    return len(fa & fb) / min(len(fa), len(fb))


def copy_mark(source: str, others: list[str], language: str = "python") -> bool:
    """Compared only with solutions in the same language: a port to another language is not a copy."""
    same = [other for other in others if source_language(other) == language]
    return any(similar(source, other, language) >= THRESHOLD for other in same)
