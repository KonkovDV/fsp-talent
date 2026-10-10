"""Optional pair model for the query and the skill text.

Off unless CROSS_ENCODER_MODE=model and CROSS_ENCODER_MODEL names a local model,
for example BAAI/bge-reranker-v2-m3. A missing library or a missing weight file
leaves the list as it was.

When it is on, it reorders the first 50 of the query ranking. Everyone else keeps
the first-stage order behind that head. Skills, grade, role and the FSP axis
are not arguments of this map.
"""
from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

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


def _open(name: str, device: str):
    import torch
    from sentence_transformers import CrossEncoder

    extra = {"model_kwargs": {"torch_dtype": torch.float16}} if device == "cuda" else {}
    try:
        return CrossEncoder(name, device=device, **extra)
    except TypeError:
        model = CrossEncoder(name, device=device)
        if device == "cuda":
            model.model.half()
        return model


def load_model():
    """The pair model, or None. GPU first, half precision: the 1650 has 4 GB. Never raises."""
    global _loaded
    if not cross_enabled():
        return None
    name = settings.CROSS_ENCODER_MODEL.strip()
    if _loaded is not None and _loaded[0] == name:
        return _loaded[1]
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            model = _open(name, device)
        except Exception:
            if device != "cuda":
                raise
            logger.exception("pair model did not fit on the GPU, loading on CPU")
            model = _open(name, "cpu")
            device = "cpu"
    except Exception:
        logger.exception("pair model was not loaded")
        return None
    _loaded = (name, model)
    logger.info("pair model loaded on %s from %s", device, name)
    return model


def rank_pairs(rows: list, query: str) -> list | None:
    """Order by the pair model. None means the model is absent and the list stays."""
    model = load_model()
    if model is None:
        return None
    if not rows:
        return []
    pairs = [(query, row[1] or "") for row in rows]
    try:
        scores = model.predict(pairs, batch_size=4, show_progress_bar=False)
    except Exception:
        logger.exception("pair model did not score")
        return None
    order = sorted(range(len(rows)), key=lambda i: (-float(scores[i]), str(rows[i][0])))
    return [rows[i][0] for i in order]
