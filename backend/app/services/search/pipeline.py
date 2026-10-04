"""
Candidate search: SQL hard filters -> lexical / quality / optional dense rankings -> RRF fusion.
Final order: (skill coverage, fused score, best LCB, id). Cards are anonymous: no name, no FSP id,
evidence shown as status + year + percentile bucket instead of exact event and place.

When a discipline is selected, the quality signal (max LCB) is computed inside that discipline only:
a strong algorithmic score must not lift a candidate in a security search.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Participant, Result, Skill
from app.models.profile import CategoryAssignment, DisciplineScore, ProfileEmbedding, ProfileSearchIndex
from app.services.ai.embedder import embed, embeddings_enabled
from app.services.categorization import DISCIPLINE_LABELS
from app.services.scoring.engine import RANK_ORDER, STATUS_LABELS, percentile
from app.services.skills import extract_skills, normalize_skill

RRF_K = 60
POOL_LIMIT = 1000


def _bucket(place: int, total: int) -> str:
    p = percentile(place, total)
    for threshold, label in ((0.99, "топ-1%"), (0.95, "топ-5%"), (0.90, "топ-10%"), (0.75, "топ-25%"), (0.50, "топ-50%")):
        if p >= threshold:
            return label
    return "участие"


def _rrf(ranked_ids: list) -> dict:
    return {pid: 1.0 / (RRF_K + i + 1) for i, pid in enumerate(ranked_ids)}


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
    text = " ".join(wanted_list + ([q] if q else [])).strip()

    score_q = select(DisciplineScore.participant_id, func.max(DisciplineScore.lcb).label("max_lcb"))
    if discipline:
        score_q = score_q.where(DisciplineScore.discipline == discipline)
    max_lcb = score_q.group_by(DisciplineScore.participant_id).subquery()
    PSI = ProfileSearchIndex
    if text:
        tsq = func.websearch_to_tsquery("simple", " or ".join(text.split()))
        lex = (func.ts_rank(PSI.skills_tsv, tsq) + func.similarity(PSI.skills_text, text)).label("lex")
    else:
        lex = literal(0.0).label("lex")

    # Adult if born on or before this calendar day. Keeps search correct after a birthday
    # even when the stored is_minor flag has not been rebuilt yet.
    today = date.today()
    try:
        adult_cutoff = today.replace(year=today.year - 18)
    except ValueError:
        adult_cutoff = date(today.year - 18, 2, 28)
    adult = or_(
        and_(Participant.birth_date.is_not(None), Participant.birth_date <= adult_cutoff),
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
    stmt = stmt.order_by(lex.desc(), max_lcb.c.max_lcb.desc().nulls_last()).limit(POOL_LIMIT)
    rows = (await db.execute(stmt)).all()
    if not rows:
        return {"total": 0, "query_skills": wanted_list, "items": []}

    ids = [r.id for r in rows]
    best = {r.id: r.max_lcb for r in rows}
    fused: dict[uuid.UUID, float] = {pid: 0.0 for pid in ids}
    rankings = [sorted(ids, key=lambda i: -best[i])]
    if text:
        rankings.append(ids)  # already ordered by lexical score
    dense_hit: set = set()
    if q and embeddings_enabled():
        vec = await embed(q)
        if vec is not None:
            dense = list(await db.scalars(
                select(ProfileEmbedding.participant_id).where(ProfileEmbedding.participant_id.in_(ids))
                .order_by(ProfileEmbedding.embedding.cosine_distance(vec)).limit(200)))
            rankings.append(dense)
            dense_hit = set(dense[:20])
    for ranking in rankings:
        for pid, s in _rrf(ranking).items():
            fused[pid] += s

    have: dict[uuid.UUID, set[str]] = {}
    if wanted:
        for pid, name in await db.execute(
                select(Skill.participant_id, Skill.name).where(Skill.participant_id.in_(ids), Skill.confirmed.is_(True),
                                                               Skill.name.in_(wanted))):
            have.setdefault(pid, set()).add(name)

    ordered = sorted(ids, key=lambda i: (-len(have.get(i, ())), -fused[i], -best[i], str(i)))[:limit]
    cards = await _build_cards(db, ordered, wanted, have, dense_hit, discipline)
    # "total" is the size of the ranked pool (capped at POOL_LIMIT), not a full COUNT(*).
    return {"total": len(ids), "pool_capped": len(ids) >= POOL_LIMIT, "query_skills": wanted_list, "items": cards}


async def _build_cards(db, ordered, wanted, have, dense_hit, discipline_filter) -> list[dict]:
    parts = {p.id: p for p in await db.scalars(select(Participant).where(Participant.id.in_(ordered)))}
    cats = {c.participant_id: c for c in await db.scalars(
        select(CategoryAssignment).where(CategoryAssignment.participant_id.in_(ordered)))}
    scores: dict = {}
    for ds in await db.scalars(select(DisciplineScore).where(DisciplineScore.participant_id.in_(ordered))
                               .order_by(DisciplineScore.lcb.desc())):
        scores.setdefault(ds.participant_id, []).append(ds)
    event_ids = [uuid.UUID(e) for lst in scores.values() for ds in lst for e in ds.top_event_ids]
    results = {r.id: r for r in await db.scalars(select(Result).where(Result.id.in_(event_ids)))} if event_ids else {}

    cards = []
    for pid in ordered:
        p, cat, matched = parts[pid], cats.get(pid), sorted(have.get(pid, ()))
        why: list[str] = []
        if wanted:
            why.append(f"Навыки: {len(matched)} из {len(wanted)}" + (f" ({', '.join(matched)})" if matched else ""))
        disciplines = []
        for ds in scores.get(pid, []):
            evidence = [{"status": STATUS_LABELS.get(r.competition_status, r.competition_status),
                         "year": r.event_date.year, "bucket": _bucket(r.place, r.total_participants),
                         "team": r.team_size > 1}
                        for e in ds.top_event_ids if (r := results.get(uuid.UUID(e)))]
            disciplines.append({"discipline": ds.discipline, "label": DISCIPLINE_LABELS.get(ds.discipline, ds.discipline),
                                "score": ds.score, "lcb": ds.lcb, "confidence": ds.confidence,
                                "best_rank": ds.best_rank, "events_count": ds.events_count, "evidence": evidence})
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
