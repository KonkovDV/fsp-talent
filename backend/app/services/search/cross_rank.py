"""Optional pair score for the query and the skill text.

Off unless CROSS_ENCODER_MODE=model and CROSS_ENCODER_MODEL names a local model.
A missing library or a missing weight file leaves the list as it was.
The match total is not replaced: only the query signal moves, and only then.
"""
from __future__ import annotations

from app.core.config import settings

PAIR_SHARE = 0.10
_loaded: tuple[str, object] | None = None


def cross_enabled() -> bool:
    return settings.CROSS_ENCODER_MODE == "model" and bool(settings.CROSS_ENCODER_MODEL.strip())


def blend_pair(fused: dict, pair_order: list | None) -> dict:
    if not pair_order:
        return fused
    ranks = {pid: index for index, pid in enumerate(pair_order)}
    out = {pid: (1.0 - PAIR_SHARE) * weight for pid, weight in fused.items()}
    for pid, index in ranks.items():
        out[pid] = out.get(pid, 0.0) + PAIR_SHARE * (1.0 / (60 + index + 1))
    return out


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
            return float(model.predict([pair])[0])
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
