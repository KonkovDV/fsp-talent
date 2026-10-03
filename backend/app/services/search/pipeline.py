"""
Hybrid search pipeline: Sparse BM25/FTS + Dense ANN, fused with RRF.

Stages
------
1. Sparse  – pg_trgm + to_tsquery (GIN index on profile_search_index)
2. Dense   – pgvector HNSW cosine ANN on profile_embeddings
3. RRF     – Reciprocal-Rank Fusion (k=60) normalises two ranked lists
4. Load    – fetch only matching scoring rows; build anonymised cards

All DB queries respect `is_visible=True` and `discoverable=True` so minor
candidates without consent cannot appear in employer results.

Vector CAST note
----------------
PostgreSQL pgvector requires the query vector to have an explicit type when
passed as a bound parameter.  Always use::

    from sqlalchemy import cast as sa_cast
    from pgvector.sqlalchemy import Vector
    ...cosine_distance(sa_cast(vec, Vector(DIM)))...

Omitting the cast may silently produce wrong results or fail with
``operator does not exist: vector <=> bytea`` on some pgvector versions.
"""
from __future__ import annotations
import logging
import uuid
from dataclasses import dataclass
from typing import Sequence

from pgvector.sqlalchemy import Vector
from sqlalchemy import cast as sa_cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.participant import Participant
from app.models.profile import ProfileEmbedding, ProfileSearchIndex
from app.services.scoring.engine import (
    DisciplineScore,
    RRF_K,
    compute_discipline_score,
    classify_grade,
)

logger = logging.getLogger(__name__)

EMBEDDING_DIM: int = settings.EMBEDDING_DIM


@dataclass(slots=True)
class SearchCard:
    """Anonymised result card – never includes display_name or contact info."""
    participant_id: uuid.UUID
    primary_role: str
    grade: str
    discipline: str
    fsp_level: str | None
    score: float
    lcb: float
    matched_skills: list[str]
    rrf_rank: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rrf(sparse_ranks: dict[uuid.UUID, int], dense_ranks: dict[uuid.UUID, int], k: int = RRF_K) -> list[uuid.UUID]:
    """Reciprocal-Rank Fusion – returns participant IDs ordered by fused score."""
    ids = set(sparse_ranks) | set(dense_ranks)
    fused = {
        pid: (1.0 / (k + sparse_ranks.get(pid, len(sparse_ranks) + k)))
             + (1.0 / (k + dense_ranks.get(pid, len(dense_ranks) + k)))
        for pid in ids
    }
    return sorted(fused, key=lambda pid: fused[pid], reverse=True)


def _pg_tsquery(text_input: str) -> str:
    """Build a safe tsquery string via websearch_to_tsquery semantics.

    We pass ``func.websearch_to_tsquery`` at the SQLAlchemy level so the DB
    handles quoting, stopwords, and morphology correctly.
    """
    return text_input.strip()


async def _sparse_search(
    db: AsyncSession,
    query: str,
    candidate_ids: Sequence[uuid.UUID],
    limit: int = 200,
) -> list[uuid.UUID]:
    """FTS + trigram sparse retrieval.

    Uses ``websearch_to_tsquery`` which handles multi-word phrases and
    negation correctly.  Falls back to an empty list on any FTS error.
    """
    if not query.strip():
        return []

    # websearch_to_tsquery handles phrases (double-quotes), negation (-), OR.
    # Use `english` config for English tokens; `russian` for Russian; `simple` as safe default.
    tsq = func.websearch_to_tsquery("simple", query)

    stmt = (
        select(ProfileSearchIndex.participant_id)
        .where(
            ProfileSearchIndex.participant_id.in_(candidate_ids),
            ProfileSearchIndex.search_vector.op("@@")(tsq),
        )
        .order_by(
            func.ts_rank_cd(ProfileSearchIndex.search_vector, tsq).desc()
        )
        .distinct()
        .limit(limit)
    )
    try:
        rows = await db.scalars(stmt)
        return list(rows)
    except Exception:
        logger.exception("Sparse search failed; returning empty list")
        return []


async def _dense_search(
    db: AsyncSession,
    vec: list[float],
    candidate_ids: Sequence[uuid.UUID],
    limit: int = 200,
) -> list[uuid.UUID]:
    """ANN cosine search via HNSW index.

    The explicit ``sa_cast(vec, Vector(DIM))`` is mandatory: without it,
    pgvector may receive a bytea-bound parameter and fall back to a sequential
    scan or raise an operator mismatch error.
    """
    if not vec:
        return []

    vec_param = sa_cast(vec, Vector(EMBEDDING_DIM))

    stmt = (
        select(ProfileEmbedding.participant_id)
        .where(ProfileEmbedding.participant_id.in_(candidate_ids))
        .order_by(ProfileEmbedding.embedding.cosine_distance(vec_param))
        .limit(limit)
    )
    rows = await db.scalars(stmt)
    return list(rows)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def search(
    db: AsyncSession,
    query: str,
    embedding: list[float] | None,
    *,
    discipline: str | None = None,
    role: str | None = None,
    grade: str | None = None,
    limit: int = 20,
) -> list[SearchCard]:
    """Run hybrid search and return anonymised scored cards.

    Parameters
    ----------
    db:
        Async SQLAlchemy session.
    query:
        Free-form text query (may be empty if embedding is provided).
    embedding:
        Query embedding vector.  Must have length == settings.EMBEDDING_DIM.
    discipline / role / grade:
        Optional hard filters applied to the candidate pool before retrieval.
    limit:
        Max results to return (default 20, max 100).
    """
    if not query.strip() and not embedding:
        return []

    limit = min(limit, 100)

    # -----------------------------------------------------------------------
    # Step 1: Build the discoverable candidate pool
    # -----------------------------------------------------------------------
    pool_stmt = select(Participant.id).where(
        Participant.is_visible.is_(True),
        # Minor without consent is excluded via discoverable property semantics
        # (is_minor=True AND minor_consent_given=False => is_visible stays True
        # but discoverable=False; we replicate that SQL-side).
        ~(
            Participant.is_minor.is_(True)
            & Participant.minor_consent_given.is_(False)
        ),
    )
    if role:
        pool_stmt = pool_stmt.where(
            Participant.id.in_(
                select(text("participant_id")).select_from(
                    text("category_assignments")
                ).where(text(f"primary_role = :role")).bindparams(role=role)
            )
        )
    if grade:
        pool_stmt = pool_stmt.where(
            Participant.id.in_(
                select(text("participant_id")).select_from(
                    text("category_assignments")
                ).where(text(f"grade = :grade")).bindparams(grade=grade)
            )
        )

    pool_ids = list(await db.scalars(pool_stmt))
    if not pool_ids:
        return []

    # -----------------------------------------------------------------------
    # Step 2: Retrieve — sparse and dense in parallel
    # -----------------------------------------------------------------------
    sparse_ids = await _sparse_search(db, query, pool_ids)
    dense_ids = await _dense_search(db, embedding or [], pool_ids)

    if not sparse_ids and not dense_ids:
        return []

    sparse_ranks = {pid: r + 1 for r, pid in enumerate(sparse_ids)}
    dense_ranks = {pid: r + 1 for r, pid in enumerate(dense_ids)}
    fused_ids = _rrf(sparse_ranks, dense_ranks)[:limit * 3]

    # -----------------------------------------------------------------------
    # Step 3: Load scoring rows and build anonymised cards
    # -----------------------------------------------------------------------
    return await _build_cards(db, fused_ids, discipline, limit)


async def _build_cards(
    db: AsyncSession,
    ordered_ids: list[uuid.UUID],
    discipline_filter: str | None,
    limit: int,
) -> list[SearchCard]:
    """Load scoring data and assemble anonymised result cards."""
    if not ordered_ids:
        return []

    # Load category assignments
    cat_rows = await db.execute(
        select(
            text("participant_id, primary_role, grade, stack"),
        ).select_from(text("category_assignments")).where(
            text("participant_id = ANY(:ids)").bindparams(ids=list(map(str, ordered_ids)))
        )
    )
    cats = {row.participant_id: row for row in cat_rows}

    # Load discipline scores
    ds_rows = await db.execute(
        select(
            text("participant_id, discipline, score, lcb, sigma, confidence, fsp_level, top_event_ids"),
        ).select_from(text("discipline_scores")).where(
            text("participant_id = ANY(:ids)").bindparams(ids=list(map(str, ordered_ids)))
        )
    )
    ds_by_pid: dict[uuid.UUID, list[DisciplineScore]] = {}
    for row in ds_rows:
        pid = row.participant_id if isinstance(row.participant_id, uuid.UUID) else uuid.UUID(str(row.participant_id))
        ds_by_pid.setdefault(pid, []).append(
            DisciplineScore(
                discipline=row.discipline,
                score=float(row.score),
                lcb=float(row.lcb),
                sigma=float(row.sigma),
                confidence=float(row.confidence),
                fsp_level=row.fsp_level,
                top_event_ids=[str(e) for e in (row.top_event_ids or [])],
            )
        )

    # Load confirmed skills (names only)
    skills_rows = await db.execute(
        select(text("participant_id, name")).select_from(text("skills")).where(
            text("participant_id = ANY(:ids) AND confirmed = TRUE").bindparams(
                ids=list(map(str, ordered_ids))
            )
        )
    )
    skills_by_pid: dict[uuid.UUID, list[str]] = {}
    for row in skills_rows:
        pid = row.participant_id if isinstance(row.participant_id, uuid.UUID) else uuid.UUID(str(row.participant_id))
        skills_by_pid.setdefault(pid, []).append(row.name)

    cards: list[SearchCard] = []
    for rank, pid in enumerate(ordered_ids, start=1):
        cat = cats.get(pid)
        if not cat:
            continue

        disciplines = ds_by_pid.get(pid, [])
        if discipline_filter:
            disciplines = [d for d in disciplines if d.discipline == discipline_filter]

        best_ds = max(disciplines, key=lambda d: d.lcb, default=None)
        grade = classify_grade(best_ds.lcb) if best_ds else (cat.grade if cat else "junior")
        fsp_level = best_ds.fsp_level if best_ds else None
        disc_name = best_ds.discipline if best_ds else "unknown"
        lcb = best_ds.lcb if best_ds else 0.0
        score = best_ds.score if best_ds else 0.0

        cards.append(
            SearchCard(
                participant_id=pid,
                primary_role=cat.primary_role if cat else "fullstack",
                grade=grade,
                discipline=disc_name,
                fsp_level=fsp_level,
                score=round(score, 4),
                lcb=round(lcb, 4),
                matched_skills=skills_by_pid.get(pid, [])[:10],
                rrf_rank=rank,
            )
        )
        if len(cards) >= limit:
            break

    return cards
