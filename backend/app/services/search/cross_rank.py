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
_loaded: tuple[str, str, object] | None = None
_running: str | None = None


def cross_enabled() -> bool:
    return settings.CROSS_ENCODER_MODE == "model" and bool(settings.CROSS_ENCODER_MODEL.strip())


def resolve_device(asked: str, cuda_ok: bool) -> str:
    """cpu forces the processor. gpu and auto use the video card when it is visible."""
    name = (asked or "auto").strip().lower()
    if name == "cpu" or not cuda_ok:
        return "cpu"
    if name in ("gpu", "cuda", "auto"):
        return "cuda"
    return "cpu"


def pair_device() -> str | None:
    """Where the loaded pair model is running. None until a search has loaded it."""
    return _running


def _cuda_ok() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


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
    """The pair model, or None. Half precision on the GPU: the 1650 has 4 GB. Never raises."""
    global _loaded, _running
    if not cross_enabled():
        return None
    name = settings.CROSS_ENCODER_MODEL.strip()
    device = resolve_device(settings.CROSS_ENCODER_DEVICE, _cuda_ok())
    if _loaded is not None and _loaded[0] == name and _loaded[1] == device:
        return _loaded[2]
    try:
        try:
            model = _open(name, device)
        except Exception:
            if device != "cuda":
                raise
            logger.exception("pair model did not fit on the GPU, loading on CPU")
            device = "cpu"
            model = _open(name, device)
    except Exception:
        logger.exception("pair model was not loaded")
        _loaded = None
        _running = None
        return None
    _loaded = (name, device, model)
    _running = device
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
