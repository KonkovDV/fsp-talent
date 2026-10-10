"""Optional pair score for the query and the skill text.

Off unless CROSS_ENCODER_MODE=model and CROSS_ENCODER_MODEL names a local model.
A missing library or a missing weight file leaves the list as it was.
The match total is not replaced: only the query signal moves, and only then.
"""
from __future__ import annotations

from app.core.config import settings

PAIR_SHARE = 0.10


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
    """The pair model, or None. Never raises into the search."""
    if not cross_enabled():
        return None
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder(settings.CROSS_ENCODER_MODEL.strip())
    except Exception:
        return None

    def score(pair: tuple[str, str]) -> float:
        try:
            return float(model.predict([pair])[0])
        except Exception:
            return 0.0

    return score
