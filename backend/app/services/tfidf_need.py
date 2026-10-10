"""Suggest skills from a vacancy by word overlap with the skill dictionary.

No network and no paid model. A suggestion is not saved until the employer keeps it.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache

from app.services.skills import TAXONOMY

_TOKEN = re.compile(r"[a-zа-яё0-9+#.]{2,}", re.IGNORECASE)
_MIN = 0.2


def _fold(token: str) -> str:
    """Drop one trailing vowel so «кафку» meets the alias «кафка»."""
    if len(token) >= 5 and token[-1] in "аеёиоуыэюя":
        return token[:-1]
    return token


def _tokens(text: str) -> list[str]:
    return [_fold(tok.casefold()) for tok in _TOKEN.findall(text)]


@lru_cache(maxsize=1)
def _index() -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    docs = {
        name: _tokens(" ".join((name, *aliases)))
        for name, (_roles, aliases) in TAXONOMY.items()
    }
    df: dict[str, int] = {}
    for tokens in docs.values():
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1
    total = len(docs) or 1
    idf = {token: math.log((total + 1) / (count + 1)) + 1.0 for token, count in df.items()}
    vectors = {name: _weigh(tokens, idf) for name, tokens in docs.items()}
    return vectors, idf


def _weigh(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    length = sum(counts.values()) or 1
    return {token: (count / length) * idf.get(token, 0.0) for token, count in counts.items() if token in idf}


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(left[token] * right.get(token, 0.0) for token in left)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def suggest_skills(text: str, limit: int = 5) -> list[str]:
    vectors, idf = _index()
    query = _weigh(_tokens(text), idf)
    ranked = sorted(
        ((name, _cosine(query, vec)) for name, vec in vectors.items()),
        key=lambda item: (-item[1], item[0]),
    )
    return [name for name, score in ranked if score >= _MIN][:limit]
