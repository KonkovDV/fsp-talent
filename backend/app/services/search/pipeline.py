"""
Candidate search: SQL hard filters -> lexical / quality / optional dense rankings -> RRF fusion.
Final order (order_pool): the explainable match score of app.services.matching, then the fused rank,
the best LCB and the id; a cold candidate may take the last seat of a block of ten. Cards are
anonymous: no name, no FSP id, evidence shown as status + year + percentile bucket instead of
exact event and place.

When a discipline is selected, the quality signal is that discipline only.
Without the filter, a need with a profile discipline reads that discipline in full and the others at half:
a security need ranks a security result above a robotics one. Roles with no profile discipline
keep the best result across disciplines. Competition status is not part of this choice.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, bindparam, exists, func, literal, or_, select, text, tuple_
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GradeConfirmation, InterviewSlot, Offer, Participant, Result, Skill, TestSession
from app.models.profile import CategoryAssignment, DisciplineScore, ProfileEmbedding, ProfileSearchIndex
from app.services import matching as matching_service
from app.services.ai.embedder import embed, embeddings_enabled
from app.services.categorization import DISCIPLINE_LABELS
from app.services.fsp.mock import STATUS_LABELS
from app.services.fsp.relevance import lcb_for_need
from app.services.matching import (
    RELATED,
    CandidateFacts,
    NeedSpec,
    category_percentile,
    pay_counterfactual,
    reason_source,
    recommended_categories,
    skill_counterfactual,
)
from app.services.matching import score as match_score
from app.services.profile import adult_cutoff
from app.services.scoring.engine import RANK_ORDER, RESULT_CLASS_LABELS, percentile, result_class
from app.services.skills import extract_skills, normalize_skill
from app.services.survey import SPECIALIZATIONS
from app.services.tasks import card_signal
from app.services.vacancy_exam import TOPIC_LABELS

logger = logging.getLogger(__name__)


def order_pool(ids: list, scores: dict, fused: dict, best: dict, cold: set | None = None,
               tiers: dict | None = None, confirmed: dict | None = None, fits: dict | None = None) -> list:
    """Rank the whole pool, then the caller slices a page. A later page cannot reorder an earlier one.

    With tiers, the key is (−tier, −confirmed grade, −score, −fit, id): the fit decides the tier,
    and a passed test orders people inside it. Without tiers the key stays score, fused rank, LCB, id.

    `cold` holds candidates with no grade test. Each block of ten that would otherwise be all tested
    gives its last seat to the next cold candidate of the same tier, when that candidate's score
    is within 0.08. A cold candidate who already earned a seat stays there.
    """
    if tiers is None:
        ranked = sorted(ids, key=lambda i: (-scores[i], -fused.get(i, 0.0), -best.get(i, 0.0), str(i)))
    else:
        ranked = sorted(ids, key=lambda i: (
            -tiers.get(i, 0), -(confirmed or {}).get(i, 0), -scores.get(i, 0.0),
            -(fits or {}).get(i, 0.0), str(i)))
    if not cold:
        return ranked
    out = list(ranked)
    block = 10
    band = 0.08
    n = len(out)
    for end in range(block, n + 1, block):
        window = out[end - block:end]
        if any(i in cold for i in window):
            continue
        host = scores.get(out[end - 1], 0.0)
        for j in range(end, n):
            guest = out[j]
            if guest not in cold or scores.get(guest, 0.0) < host - band:
                continue
            if tiers is not None and tiers.get(guest, 0) != tiers.get(out[end - 1], 0):
                continue
            out[end - 1], out[j] = guest, out[end - 1]
            break
    return out


def days_ago(moment: datetime, now: datetime | None = None) -> str:
    """How fresh a signal is, in words an HR reads at a glance."""
    days = ((now or datetime.now(UTC)) - moment).days
    if days <= 0:
        return "сегодня"
    if days == 1:
        return "вчера"
    return f"{days} дн. назад"

RRF_K = 60
POOL_LIMIT = 1000
DENSE_POOL = 300


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
    """Quote skill names so to_tsquery accepts C++, C# and Node.js.

    The simple-dictionary tsvector keeps the same tokens the parser extracts
    from the stored skill text. Renaming C++ to cpp would miss that index.
    """
    quoted = []
    for name in names:
        lexeme = name.replace("\\", "").replace("'", "''")
        if lexeme:
            quoted.append(f"'{lexeme}'")
    return " | ".join(quoted) or None


def _safe_uuid(s: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(s))
    except (ValueError, AttributeError):
        logger.warning("Skipping malformed UUID in top_event_ids: %r", s)
        return None


BANK_MIN = 5   # a cell with fewer people is hidden, so a count cannot point at one person


def bank_cells(rows: list[tuple[str | None, str | None, int, int]], min_n: int = BANK_MIN) -> list[dict]:
    """Rows (role, grade, people, tested) -> visible cells of the role × grade showcase."""
    cells = []
    for role, grade, people, tested in rows:
        if not role or not grade:
            continue
        hidden = people < min_n
        cells.append({"role": role, "grade": grade, "hidden": hidden,
                      "candidates": None if hidden else people, "tested": None if hidden else tested})
    return cells


def created_after(now: datetime, fresh_days: int | None) -> datetime | None:
    """Lower bound for «новые за N дней». None means the filter is off."""
    if not fresh_days:
        return None
    return now - timedelta(days=fresh_days)


def _in_search(adult):
    """Who an employer may see: the card is published, age allows it, the person is not «не ищу»,
    and the grade was chosen in the survey or confirmed by the test.

    The showcase uses this same predicate, so a profile that only has FSP protocols is not counted.
    """
    graded = exists(select(CategoryAssignment.id).where(
        CategoryAssignment.participant_id == Participant.id,
        CategoryAssignment.grade_source.in_(("declared", "assessed")),
    ))
    return and_(
        Participant.is_visible.is_(True),
        Participant.job_search != "not_looking",
        or_(adult, Participant.minor_consent_given.is_(True)),
        graded,
    )


async def bank_grid(db: AsyncSession) -> dict:
    """The candidate bank by specialization and grade: who is in search and how many confirmed the grade by test.

    Same visibility as the search itself, including the survey-or-test grade inside ``_in_search``.
    """
    cutoff = adult_cutoff()
    adult = or_(
        and_(Participant.birth_date.is_not(None), Participant.birth_date <= cutoff),
        and_(Participant.birth_date.is_(None), Participant.is_minor.is_(False)),
    )
    PSI = ProfileSearchIndex
    tested = func.count(Participant.assessed_grade).filter(PSI.grade == Participant.assessed_grade)
    rows = (await db.execute(
        select(PSI.role, PSI.grade, func.count(), tested)
        .join(Participant, Participant.id == PSI.participant_id)
        .where(_in_search(adult))
        .group_by(PSI.role, PSI.grade))).all()
    return {"min_cell": BANK_MIN, "cells": bank_cells([tuple(r) for r in rows])}


async def search_candidates(
    db: AsyncSession,
    role: str | None = None,
    grade: str | None = None,
    discipline: str | None = None,
    min_rank: str | None = None,
    skills: list[str] | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fresh_days: int | None = None,
    assessed_only: bool = False,
    has_fsp: bool | None = None,
    work_goal: str | None = None,
    need: NeedSpec | None = None,
    employer_id: uuid.UUID | None = None,
    build_cards: bool = True,
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
            # Related technologies are retrieved too: the factor score gives them half credit.
            retrieval = set(wanted_list) | (set(need.nice) if need else set())
            for group in RELATED:
                if retrieval & group:
                    retrieval |= group
            skill_q = _skill_or_tsquery(sorted(retrieval))
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
            .where(_in_search(adult)))
    if since := created_after(datetime.now(UTC), fresh_days):
        stmt = stmt.where(Participant.created_at >= since)
    if assessed_only:
        stmt = stmt.where(Participant.assessed_grade.is_not(None))
    if has_fsp is not None:
        stmt = stmt.where(Participant.fsp_id.is_not(None) if has_fsp else Participant.fsp_id.is_(None))
    if work_goal == "internship":
        # Internship mode: students who look for practice or either option.
        stmt = stmt.where(Participant.work_goal.in_(("internship", "both")))
    elif work_goal == "job":
        stmt = stmt.where(or_(Participant.work_goal.is_(None), Participant.work_goal.in_(("job", "both"))))
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
                .where(_in_search(adult))
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

    # TZ: inside a category, better test results rank higher. theta is on one IRT scale for every
    # session, so the best completed result is comparable across candidates. Only the primary test of the
    # specialization counts: a test built from a vacancy is practice and does not move the candidate.
    # A jury trial stores an ability estimate for the candidate's own screen and must not move the ranking.
    not_trial = or_(TestSession.flags["mode"].astext.is_(None), TestSession.flags["mode"].astext != "express")
    test_theta: dict[uuid.UUID, float] = {
        pid: theta for pid, theta in await db.execute(
            select(TestSession.participant_id, func.max(TestSession.irt_theta))
            .where(TestSession.participant_id.in_(list(ids_set)), TestSession.status == "completed",
                   TestSession.irt_theta.is_not(None), not_trial, ~TestSession.flags.has_key("vacancy_id"))
            .group_by(TestSession.participant_id))
    }
    if test_theta:
        rankings.append(sorted(test_theta, key=lambda i: -test_theta[i]))

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

    need = need or NeedSpec(role=role, grade=grade, skills=tuple(wanted_list), text=bool(q))
    matches = await score_pool(db, all_ids, need, fused, discipline, employer_id)
    facts = [matches[i].facts for i in all_ids if matches[i].facts]
    pay_hint = pay_counterfactual(need, facts)
    skill_hint = skill_counterfactual(need, facts)
    cold = {i for i in all_ids if matches[i].facts and matches[i].facts.test_p is None}
    # One explainable score orders the list; ties fall back to the fused retrieval rank.
    # Untested candidates take one seat in a block of ten when they are close.
    score_of = {i: matches[i].score for i in all_ids}
    if matching_service.USE_FIT_TIERS:
        ordered = order_pool(
            all_ids, score_of, fused, best, cold,
            tiers={i: matches[i].tier or 0 for i in all_ids},
            confirmed={i: matches[i].confirmed for i in all_ids},
            fits={i: matches[i].fit or 0.0 for i in all_ids})
    else:
        ordered = order_pool(all_ids, score_of, fused, best, cold)
    categories = recommended_categories(
        [(f.role, f.grade, matches[i].score) for i in ordered[:200] if (f := matches[i].facts)],
        min_n=BANK_MIN)
    header = {"total": len(all_ids), "pool_capped": len(rows) >= POOL_LIMIT, "query_skills": wanted_list,
              "recommended_categories": categories, "pay_hint": pay_hint, "skill_hint": skill_hint}
    if not build_cards:
        # The cache keeps the order and the scores. Cards for one page are built later.
        items = []
        for pid in ordered[:limit]:
            m = matches[pid]
            items.append({
                "candidate_id": str(pid),
                "have": sorted(have.get(pid, ())),
                "skill_evidence": dict(m.facts.skills) if m.facts else {},
                "match": {"score": m.score, "basis": m.basis, "plus": m.plus, "minus": m.minus, "info": m.info,
                          "reasons": [{"code": r.code, "text": r.text, "tone": r.tone,
                                       "source": reason_source(r.code), "points": r.points} for r in m.reasons],
                          "factors": [{"key": f.key, "label": f.label, "weight": f.weight, "value": f.value}
                                      for f in m.factors]},
            })
        return {**header, "items": items}
    ordered = ordered[offset:offset + limit]
    cards = await _build_cards(db, ordered, wanted, have, dense_hit, discipline)
    for card in cards:
        m = matches[uuid.UUID(card["candidate_id"])]
        card["match"] = {"score": m.score, "basis": m.basis, "plus": m.plus, "minus": m.minus, "info": m.info,
                         "reasons": [{"code": r.code, "text": r.text, "tone": r.tone,
                                      "source": reason_source(r.code), "points": r.points} for r in m.reasons],
                         "factors": [{"key": f.key, "label": f.label, "weight": f.weight, "value": f.value}
                                     for f in m.factors]}
        card["skill_evidence"] = dict(m.facts.skills) if m.facts else {}
    return {"total": len(all_ids), "pool_capped": len(rows) >= POOL_LIMIT, "query_skills": wanted_list,
            "recommended_categories": categories, "pay_hint": pay_hint, "skill_hint": skill_hint,
            "items": cards}


@dataclass
class PoolMatch:
    score: float
    factors: list
    plus: list
    minus: list
    info: list
    facts: CandidateFacts | None
    basis: str = "fit"
    reasons: list | None = None
    fit: float | None = None
    tier: int | None = None
    confirmed: int = 0


async def _interview_outcomes(db: AsyncSession, employer_id: uuid.UUID, ids: list[uuid.UUID]) -> dict:
    """Latest decided meeting of this company. A company the candidate has not met does not appear."""
    found: dict[uuid.UUID, tuple] = {}
    rows = await db.execute(
        select(Offer.candidate_id, InterviewSlot.outcome, InterviewSlot.outcome_at)
        .join(InterviewSlot, InterviewSlot.offer_id == Offer.id)
        .where(Offer.employer_id == employer_id, Offer.candidate_id.in_(ids),
               InterviewSlot.chosen.is_(True), InterviewSlot.outcome.is_not(None)))
    for pid, outcome, at in rows:
        prev = found.get(pid)
        if prev is None or (at or datetime.min.replace(tzinfo=UTC)) >= (prev[1] or datetime.min.replace(tzinfo=UTC)):
            found[pid] = (outcome, at)
    return {pid: outcome for pid, (outcome, _) in found.items()}


async def score_pool(db: AsyncSession, ids: list[uuid.UUID], need: NeedSpec, fused: dict[uuid.UUID, float],
                     discipline: str | None = None, employer_id: uuid.UUID | None = None) -> dict[uuid.UUID, PoolMatch]:
    """Load the facts the factor score needs for every candidate of the pool, in four queries."""
    if not ids:
        return {}
    names = set(need.skills) | set(need.nice)
    for group in RELATED:
        if names & group:
            names |= group
    skills: dict[uuid.UUID, dict[str, str]] = {}
    if names:
        for pid, name, trust in await db.execute(
                select(Skill.participant_id, Skill.name, Skill.trust_level).where(
                    Skill.participant_id.in_(ids), Skill.confirmed.is_(True), Skill.name.in_(names))):
            skills.setdefault(pid, {})[name] = trust
    people = {p.id: p for p in await db.scalars(select(Participant).where(Participant.id.in_(ids)))}
    cats = {c.participant_id: c for c in await db.scalars(
        select(CategoryAssignment).where(CategoryAssignment.participant_id.in_(ids)))}
    by_discipline: dict[uuid.UUID, dict[str, float]] = {}
    for pid, disc, value in await db.execute(
            select(DisciplineScore.participant_id, DisciplineScore.discipline, DisciplineScore.lcb).where(
                DisciplineScore.participant_id.in_(ids))):
        by_discipline.setdefault(pid, {})[disc] = float(value or 0.0)
    confs = {(c.participant_id, c.specialization): c for c in await db.scalars(
        select(GradeConfirmation).where(GradeConfirmation.participant_id.in_(ids)))}
    pending = {pid: n for pid, n in await db.execute(
        select(Offer.candidate_id, func.count()).where(
            Offer.candidate_id.in_(ids), Offer.status == "pending").group_by(Offer.candidate_id))}
    refusals = {pid: n for pid, n in await db.execute(
        select(Offer.candidate_id, func.count()).where(
            Offer.candidate_id.in_(ids), Offer.status == "rejected",
            Offer.decline_reason == "salary").group_by(Offer.candidate_id))}
    session_ids = [c.session_id for c in confs.values() if c.session_id]
    counts: dict[uuid.UUID, tuple[int, int]] = {}
    if session_ids:
        # Item rows hide answer keys from employers. The aggregate returns only counts
        # and puts the row-level bypass back before the request continues.
        counts_query = text(
            "SELECT session_id, n, correct FROM app_answer_counts(:ids)"
        ).bindparams(bindparam("ids", type_=ARRAY(PG_UUID(as_uuid=True))))
        for sid, n, correct in await db.execute(counts_query, {"ids": session_ids}):
            counts[sid] = (int(correct or 0), int(n or 0))
    interviews = await _interview_outcomes(db, employer_id, ids) if employer_id else {}
    top = max(fused.values(), default=0.0) or 1.0
    out: dict[uuid.UUID, PoolMatch] = {}
    for pid in ids:
        p, cat = people.get(pid), cats.get(pid)
        spec = need.role or (p.specialization if p else None) or (cat.primary_role if cat else None)
        conf = confs.get((pid, spec)) if spec else None
        has_fsp = bool(p and p.fsp_id)
        if has_fsp:
            fsp_lcb, fsp_kind, fsp_discipline = lcb_for_need(need.role, by_discipline.get(pid, {}), discipline)
        else:
            fsp_lcb, fsp_kind, fsp_discipline = None, None, None
        facts = CandidateFacts(
            role=cat.primary_role if cat else None, grade=cat.grade if cat else None,
            grade_source=cat.grade_source if cat else None, skills=skills.get(pid, {}),
            test_p=conf.p_pass if conf and conf.p_pass is not None else (1.0 if conf else None),
            test_spec=conf.specialization if conf else None,
            fsp_lcb=fsp_lcb, fsp_kind=fsp_kind, fsp_discipline=fsp_discipline,
            industry=p.industry if p else None,
            text_rank=fused.get(pid, 0.0) / top,
            salary_from=p.salary_from_gross if p else None, salary_to=p.salary_to_gross if p else None,
            test_se=conf.se if conf and conf.se else None,
            test_correct=counts.get(conf.session_id, (None, None))[0] if conf and conf.session_id else None,
            test_n=counts.get(conf.session_id, (None, None))[1] if conf and conf.session_id else None,
            open_invites=int(pending.get(pid, 0)),
            salary_refusals=int(refusals.get(pid, 0)),
            job_search=(p.job_search if p else None) or "open",
            interview_outcome=interviews.get(pid),
        )
        m = match_score(need, facts)
        out[pid] = PoolMatch(m.score, m.factors, m.plus, m.minus, m.info, facts, m.basis, m.reasons,
                             m.fit, m.tier, m.confirmed)
    return out


async def _category_percentiles(db, cats: dict) -> dict:
    """One query: where each confirmed candidate stands inside role × grade, by test probability."""
    keys = {(c.primary_role, c.grade) for c in cats.values() if c and c.primary_role and c.grade}
    if not keys:
        return {}
    rows = await db.execute(
        select(CategoryAssignment.participant_id, CategoryAssignment.primary_role,
               CategoryAssignment.grade, GradeConfirmation.p_pass)
        .join(GradeConfirmation, and_(
            GradeConfirmation.participant_id == CategoryAssignment.participant_id,
            GradeConfirmation.specialization == CategoryAssignment.primary_role,
        ))
        .where(tuple_(CategoryAssignment.primary_role, CategoryAssignment.grade).in_(list(keys)))
    )
    groups: dict[tuple, list[tuple]] = {}
    for pid, role, grade, p_pass in rows:
        if p_pass is None:
            continue
        groups.setdefault((role, grade), []).append((pid, float(p_pass)))
    out = {}
    for (role, grade), members in groups.items():
        label = f"{SPECIALIZATIONS.get(role, role)} × {grade}"
        for pid, value in members:
            others = [item for other, item in members if other != pid]
            pct = category_percentile(value, others)
            if pct is not None:
                out[pid] = f"Лучше {pct} % кандидатов категории {label}"
    return out


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
    percentiles = await _category_percentiles(db, cats)

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
                 "result": RESULT_CLASS_LABELS[result_class(r.place, r.total_participants)],
                 "team": r.team_size > 1}
                for e in ds.top_event_ids
                if (uid := _safe_uuid(e)) and (r := results.get(uid))
            ]
            disciplines.append({"discipline": ds.discipline,
                                "label": DISCIPLINE_LABELS.get(ds.discipline, ds.discipline),
                                "score": ds.score, "lcb": ds.lcb, "confidence": ds.confidence,
                                "best_rank": ds.best_rank,
                                "rank_assigned_at": ds.rank_assigned_at.isoformat() if ds.rank_assigned_at else None,
                                "rank_order_ref": ds.rank_order_ref,
                                "events_count": ds.events_count, "evidence": evidence})
        if cat and cat.grade_source == "assessed":
            why.append(f"Грейд {cat.grade} подтверждён тестом")
        if disciplines:
            top = next((d for d in disciplines if d["discipline"] == discipline_filter), disciplines[0])
            if top["best_rank"]:
                why.append(f"Присвоенный разряд {top['best_rank']} ({top['label']})")
            why.append(f"Подтверждено ФСП: нижняя граница уровня {top['lcb']:.2f}, "
                       f"уверенность {round(top['confidence'] * 100)}%, событий {top['events_count']}")
        if pid in dense_hit:
            why.append("Смысловое совпадение с запросом")
        if p.practice_at is not None and p.practice_topic:
            mark = "верно" if p.practice_ok else "с ошибкой"
            topic = TOPIC_LABELS.get(p.practice_topic, p.practice_topic)
            why.append(f"Короткая практика ({topic}): {mark}, {days_ago(p.practice_at)}")
        if task_line := card_signal(p, days_ago):
            why.append(task_line)
        line = percentiles.get(pid)
        if line:
            why.append(line)
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
