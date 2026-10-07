"""Okapi BM25 over short skill texts.

The stand's search still ranks words with PostgreSQL ts_rank and trigrams (RRF k = 60). This function
is the ablation: it is not called from the published ranker, so the matching table does not move.
"""
from __future__ import annotations

import math
import re

_TOKEN = re.compile(r"[0-9A-Za-zА-Яа-яЁё+#.]{2,}")


def tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN.finditer(text or "")]


def bm25(query: str, documents: list[str], *, k1: float = 1.2, b: float = 0.75) -> list[float]:
    """Score each document against the query. An empty corpus returns an empty list."""
    docs = [tokens(doc) for doc in documents]
    query_terms = tokens(query)
    n = len(docs)
    if n == 0:
        return []
    avg = sum(len(doc) for doc in docs) / n
    df: dict[str, int] = {}
    for doc in docs:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1
    scores: list[float] = []
    for doc in docs:
        tf: dict[str, int] = {}
        for term in doc:
            tf[term] = tf.get(term, 0) + 1
        length = len(doc) or 1
        score = 0.0
        for term in query_terms:
            freq = tf.get(term)
            if not freq:
                continue
            idf = math.log(1.0 + (n - df[term] + 0.5) / (df[term] + 0.5))
            denom = freq + k1 * (1.0 - b + b * length / avg)
            score += idf * (freq * (k1 + 1.0)) / denom
        scores.append(score)
    return scores
