"""Optional pair model for the query and the skill text.

Off unless CROSS_ENCODER_MODE=model and CROSS_ENCODER_MODEL names a local model,
for example BAAI/bge-reranker-v2-m3. A missing library or a missing weight file
leaves the list as it was.

When it is on, it reorders the first 50 of the query ranking. Everyone else keeps
the first-stage order behind that head. Skills, grade, role and the FSP axis
are not arguments of this map.
"""
from __future__ import annotations

from app.core.config import settings

RERANK_HEAD = 50
_RRF_K = 60
_loaded: tuple[str, object] | None = None


def cross_enabled() -> bool:
    return settings.CROSS_ENCODER_MODE == "model" and bool(settings.CROSS_ENCODER_MODEL.strip())


def rerank_text(fused: dict, pair_order: list | None) -> dict:
    """Query order after the pair model. No pair order leaves the map unchanged."""
    if not pair_order:
        return fused
    seen: set = set()
    head = []
    for pid in pair_order:
        if pid in seen:
            continue
        seen.add(pid)
        head.append(pid)
    tail = sorted((pid for pid in fused if pid not in seen), key=lambda pid: (-fused[pid], str(pid)))
    return {pid: 1.0 / (_RRF_K + index + 1) for index, pid in enumerate(head + tail)}


def scorer():
    """The pair model, or None. Loaded once. Never raises into the search."""
    global _loaded
    if not cross_enabled():
        return None
    name = settings.CROSS_ENCODER_MODEL.strip()
    if _loaded is None or _loaded[0] != name:
        try:
            from sentence_transformers import CrossEncoder
            _loaded = (name, CrossEncoder(name))
        except Exception:
            return None
    model = _loaded[1]

    def score(pair: tuple[str, str]) -> float:
        try:
            return float(model.predict([(pair[0], pair[1])])[0])
        except Exception:
            return 0.0

    return score


def rank_pairs(rows: list, query: str) -> list | None:
    """Order by the pair model. None means the model is absent and the list stays."""
    ranker = scorer()
    if ranker is None:
        return None
    ranked = sorted(rows, key=lambda row: (-ranker((query, row[1] or "")), str(row[0])))
    return [row[0] for row in ranked]
