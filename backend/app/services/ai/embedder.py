"""
Dense embeddings for semantic search. Disabled unless EMBEDDINGS_MODE=model:
pseudo-random fallback vectors would inject noise into ranking, so without a real
model the dense stage is simply skipped.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from anyio import to_thread

from app.core.config import settings

logger = logging.getLogger(__name__)


def embeddings_enabled() -> bool:
    return settings.AI_ENABLED and settings.EMBEDDINGS_MODE == "model"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    logger.info(f"Loading embedding model {settings.EMBEDDING_MODEL}")
    return SentenceTransformer(settings.EMBEDDING_MODEL)


async def embed(text: str) -> list[float] | None:
    if not embeddings_enabled():
        return None
    try:
        vec = await to_thread.run_sync(lambda: _model().encode(text, normalize_embeddings=True))
        return vec.tolist()
    except Exception:
        logger.exception("Embedding failed, dense stage skipped")
        return None


def profile_text(skills: list[str], role: str, disciplines: list[str]) -> str:
    return f"Роль: {role}. Навыки: {', '.join(skills)}. Дисциплины ФСП: {', '.join(disciplines)}."
