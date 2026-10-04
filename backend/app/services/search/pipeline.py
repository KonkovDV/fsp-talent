"""
Candidate search: SQL hard filters -> lexical / quality / optional dense rankings -> RRF fusion.
Final order: (skill coverage, fused score, best LCB, id). Cards are anonymous: no name, no FSP id,
evidence shown as status + year + percentile bucket instead of exact event and place.

When a discipline is selected, the quality signal (max LCB) is computed inside that discipline only:
a strong algorithmic score must not lift a candidate in a security search.
"""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Participant, Result, Skill
from app.models.profile import CategoryAssignment, DisciplineScore, ProfileEmbedding, ProfileSearchIndex
from app.services.ai.embedder import embed, embeddings_enabled
from app.services.categorization import DISCIPLINE_LABELS
from app.services.profile import adult_cutoff
from app.services.scoring.engine import RANK_ORDER, STATUS_LABELS, percentile
from app.services.skills import extract_skills, normalize_skill

logger = logging.getLogger(__name__)

RRF_K = 60
POOL_LIMIT = 1000
DENSE_POOL = 300

# ---------------------------------------------------------------------------
# FIX: tsquery normalization for special-char skill names.
# PostgreSQL to_tsquery quoted lexemes only allow [a-zA-Z0-9_] and Cyrillic.
# C++ -> cpp, C# -> csharp, Node.js -> nodejs, etc.
# This map MUST be consistent with how skills_text is indexed in ProfileSearchIndex;
# see services/profile.py rebuild_profile where skills_text is set.
# ---------------------------------------------------------------------------
_SKILL_TSQUERY_MAP: dict[str, str] = {
    "C++": "cpp",
    "C#": "csharp",
    "Node.js": "nodejs",
    "Vue.js": "vuejs",
    "Next.js": "nextjs",
    "React.js": "reactjs",
    "Nuxt.js": "nuxtjs",
    "Three.js": "threejs",
    "HTML/CSS": "htmlcss",
    "scikit-learn": "sklearn",
    "PX4/ArduPilot": "px4 ardupilot",
    "Prometheus/Grafana": "prometheus grafana",
    "CI/CD": "cicd",
    "gRPC": "grpc",
    "GraphQL": "graphql",
    "WebAssembly": "wasm",
    "R": "rlang",
    "Go": "golang",
    ".NET": "dotnet",
    "ASP.NET": "aspnet",
    "F#": "fsharp",
    "Qt/C++": "qtcpp",
}


def _normalize_skill_for_tsq(skill: str) -> str:
    """Return a safe tsquery lexeme string for the skill.

    Checks the explicit map first, then falls back to stripping every character
    that PostgreSQL rejects inside a quoted tsquery lexeme (anything that is not
    alphanumeric or Cyrillic). The result is lowercased.
    """
    if skill in _SKILL_TSQUERY_MAP:
        return _SKILL_TSQUERY_MAP[skill].lower()
    normalized = re.sub(r"[^\w\u0400-\u04ff]", "", skill.lower())
    return normalized or skill.lower()[:30]


def _bucket(place: int, total: int) -> str:
    p = percentile(place, total)
    for threshold, label in ((0.99, "топ-1%"), (0.95, "топ-5%"), (0.90, "топ-10%"),
                             (0.75, "топ-25%"), (0.50, "топ-50%")):
        if p >= threshold:
            return label
    return "участие"


def _rrf(ranked_ids: list) -> dict:
    return {pid: 1.0 / (RRF_K + i + 1) for i, pid in enumerate(ranked_ids)}


def _skill_or_tsquery(names: list[str]) -> str | None:
    """Build a to_tsquery-compatible OR-expression for the given skill names.

    Each skill is normalized to strip characters that are illegal inside
    PostgreSQL tsquery quoted lexemes (C++ -> cpp, C# -> csharp, Node.js -> nodejs).
    Multi-token expansions (e.g. 'px4 ardupilot') are split into separate lexemes
    joined with the OR operator so that each token is matched independently.
    Returns None when the resulting expression would be empty.
    """
    lexemes: list[str] = []
    for name in names:
        normalized = _normalize_skill_for_tsq(name)
        if not normalized:
            continue
        for token in normalized.split():
            token = token.replace("'", "")
            if token:
                lexemes.append(f"'{token}'")
    if not lexemes:
        return None
    return " | ".join(lexemes)


def _safe_uuid(s: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(s))
    except (ValueError, AttributeError):
        logger.warning("Skipping malformed UUID in top_event_ids: %r", s)
        return None


async def search_candidates(
    db: AsyncSession,
    role: str | None = None,
    grade: str | None = None,
    discipline: str | None = None,
    min_rank: str | None = None,
    skills: list[str] | None = None,
    q: str | None = None,
    limit: int = 20,
) -> dict:
    wanted = {n for s in (skills or []) if (n := normalize_skill(s))}
    if q:
        wanted |= {e.skill for e in extract_skills(q)}
    wanted_list = sorted(wanted)

    score_q = select(DisciplineScore.participant_id, func.max(DisciplineScore.lcb).label("max_lcb"))
    if discipline:
        score_q = score_q.where(DisciplineScore.discipline == discipline)
    max_lcb = score_q.group_by(DisciplineScore.participant_id).subquery()

    PSI = ProfileSearchIndex

    tsq = None
    if wanted_list or q:
        parts: list = []
        if wanted_list:
            skill_q = _skill_or_tsquery(wanted_list)
            if skill_q:
                parts.append(func.to_tsquery("simple", skill_q))
        if q:
            parts.append(func.websearch_to_tsquery("simple", q))
        if len(parts) == 1:
            tsq = parts[0]
        elif len(parts) == 2:
            tsq = parts[0].op("||")( parts[1])
        similarity_text = q or " ".join(wanted_list)
        lex = (func.ts_rank(PSI.skills_tsv, tsq) + func.similarity(PSI.skills_text, similarity_text)).label("lex")
    else:
        lex = literal(0.0).label("lex")

    cutoff = adult_cutoff()
    adult = or_(
        and_(Participant.birth_date.is_not(None), Participant.birth_date <= cutoff),
        and_(Participant.birth_date.is_(None), Participant.is_minor.is_(False)),
    )
    stmt = (select(Participant.id, func.coalesce(max_lcb.c.max_lcb, 0.0).label("max_lcb"), lex)
            .join(PSI, PSI.participant_id == Participant.id)
            .outerjoin(max_lcb, max_lcb.c.participant_id == Participant.id)
            .where(Participant.is_visible.is_(True),
                   or_(adult, Participant.minor_consent_given.is_(True))))
    if role:
        stmt = stmt.where(PSI.role == role)
    if grade:
        stmt = stmt.where(PSI.grade == grade)
    if discipline or min_rank:
        sub = select(DisciplineScore.participant_id)
        if discipline:
            sub = sub.where(DisciplineScore.discipline == discipline)
        if min_rank in RANK_ORDER:
            sub = sub.where(DisciplineScore.best_rank.in_(RANK_ORDER[:RANK_ORDER.index(min_rank) + 1]))
        stmt = stmt.where(Participant.id.in_(sub))
    if tsq is not None:
        stmt = stmt.where(PSI.skills_tsv.op("@@")(tsq))
    stmt = stmt.order_by(lex.desc(), max_lcb.c.max_lcb.desc().nulls_last()).limit(POOL_LIMIT)
    rows = (await db.execute(stmt)).all()

    ids_set: set[uuid.UUID] = {r.id for r in rows}
    best = {r.id: r.max_lcb for r in rows}
    fused: dict[uuid.UUID, float] = {pid: 0.0 for pid in ids_set}

    rankings: list[list] = [sorted(ids_set, key=lambda i: -best[i])]
    if rows:
        rankings.append([r.id for r in rows])

    dense_hit: set = set()
    if q and embeddings_enabled():
        vec = await embed(q)
        if vec is not None:
            dense = list(await db.scalars(
                select(ProfileEmbedding.participant_id)
                .join(Participant, Participant.id == ProfileEmbedding.participant_id)
                .where(
                    Participant.is_visible.is_(True),
                    or_(adult, Participant.minor_consent_given.is_(True)),
                )
                .order_by(ProfileEmbedding.embedding.cosine_distance(vec))
                .limit(DENSE_POOL)
            ))
            rankings.append(dense)
            dense_hit = set(dense[:20])
            for pid in dense:
                if pid not in ids_set:
                    ids_set.add(pid)
                    fused[pid] = 0.0
                    best.setdefault(pid, 0.0)

    for ranking in rankings:
        for pid, s in _rrf(ranking).items():
            if pid in fused:
                fused[pid] += s

    all_ids = list(ids_set)
    have: dict[uuid.UUID, set[str]] = {}
    if wanted:
        for pid, name in await db.execute(
                select(Skill.participant_id, Skill.name).where(
                    Skill.participant_id.in_(all_ids), Skill.confirmed.is_(True), Skill.name.in_(wanted))):
            have.setdefault(pid, set()).add(name)

    ordered = sorted(all_ids, key=lambda i: (-len(have.get(i, ())), -fused[i], -best[i], str(i)))[:limit]
    cards = await _build_cards(db, ordered, wanted, have, dense_hit, discipline)
    return {"total": len(all_ids), "pool_capped": len(rows) >= POOL_LIMIT, "query_skills": wanted_list, "items": cards}


async def _build_cards(db, ordered, wanted, have, dense_hit, discipline_filter) -> list[dict]:
    parts = {p.id: p for p in await db.scalars(select(Participant).where(Participant.id.in_(ordered)))}
    cats = {c.participant_id: c for c in await db.scalars(
        select(CategoryAssignment).where(CategoryAssignment.participant_id.in_(ordered)))}
    scores: dict = {}
    for ds in await db.scalars(select(DisciplineScore).where(DisciplineScore.participant_id.in_(ordered))
                               .order_by(DisciplineScore.lcb.desc())):
        scores.setdefault(ds.participant_id, []).append(ds)

    event_ids = [
        uid for lst in scores.values()
        for ds in lst
        for e in ds.top_event_ids
        if (uid := _safe_uuid(e)) is not None
    ]
    results = {r.id: r for r in await db.scalars(select(Result).where(Result.id.in_(event_ids)))} if event_ids else {}

    cards = []
    for pid in ordered:
        p = parts.get(pid)
        if p is None:
            continue
        cat, matched = cats.get(pid), sorted(have.get(pid, ()))
        why: list[str] = []
        if wanted:
            why.append(f"Навыки: {len(matched)} из {len(wanted)}" + (f" ({', '.join(matched)})" if matched else ""))
        disciplines = []
        for ds in scores.get(pid, []):
            evidence = [
                {"status": STATUS_LABELS.get(r.competition_status, r.competition_status),
                 "year": r.event_date.year, "bucket": _bucket(r.place, r.total_participants),
                 "team": r.team_size > 1}
                for e in ds.top_event_ids
                if (uid := _safe_uuid(e)) and (r := results.get(uid))
            ]
            disciplines.append({"discipline": ds.discipline,
                                "label": DISCIPLINE_LABELS.get(ds.discipline, ds.discipline),
                                "score": ds.score, "lcb": ds.lcb, "confidence": ds.confidence,
                                "best_rank": ds.best_rank, "events_count": ds.events_count,
                                "evidence": evidence})
        if disciplines:
            top = next((d for d in disciplines if d["discipline"] == discipline_filter), disciplines[0])
            if top["best_rank"]:
                why.append(f"Разряд-эквивалент {top['best_rank']} ({top['label']})")
            why.append(f"Подтверждено ФСП: нижняя граница уровня {top['lcb']:.2f}, "
                       f"уверенность {round(top['confidence'] * 100)}%, событий {top['events_count']}")
        if pid in dense_hit:
            why.append("Смысловое совпадение с запросом")
        cards.append({
            "candidate_id": str(pid),
            "role": cat.primary_role if cat else None,
            "grade": cat.grade if cat else None,
            "grade_source": cat.grade_source if cat else None,
            "region": p.region,
            "experience_years": p.experience_years,
            "stack": cat.stack if cat else [],
            "matched_skills": matched,
            "missing_skills": sorted(wanted - set(matched)),
            "disciplines": disciplines,
            "why": why,
        })
    return cards
