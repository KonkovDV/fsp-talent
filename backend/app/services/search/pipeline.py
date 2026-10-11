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
The «Запрос» factor is only the words and the meaning of the query. The test and the FSP axis
do not enter it.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, bindparam, exists, func, literal, or_, select, text, tuple_
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    CandidateResume,
    Employer,
    GradeConfirmation,
    InterviewSlot,
    Offer,
    Participant,
    Result,
    Skill,
    TestSession,
)
from app.models.profile import CategoryAssignment, DisciplineScore, ProfileEmbedding, ProfileSearchIndex
from app.services import matching as matching_service
from app.services.ai.embedder import embed, embeddings_enabled
from app.services.ambition import ambition_note
from app.services.cat import PASS_P, is_borderline
from app.services.categorization import DISCIPLINE_LABELS
from app.services.code_profile import code_profile_line
from app.services.fsp.mock import STATUS_LABELS
from app.services.fsp.relevance import lcb_for_need
from app.services.hiring_practice import sees_senior
from app.services.matching import (
    RELATED,
    CandidateFacts,
    NeedSpec,
    category_pairs,
    category_percentile,
    pay_counterfactual,
    reason_source,
    recommended_categories,
    reply_outlook,
    skill_counterfactual,
    standing_line,
)
from app.services.matching import score as match_score
from app.services.profile import age_confirmed_adult
from app.services.scoring.elo_stretch import elo_stretch
from app.services.scoring.engine import RANK_ORDER, RESULT_CLASS_LABELS, percentile, result_class
from app.services.search.cross_rank import RERANK_HEAD, cross_enabled, pair_device, rank_pairs, rerank_text
from app.services.session_marks import latest_failed_targets, latest_grade_flags, penalised
from app.services.skills import extract_skills, normalize_skill
from app.services.survey import SPECIALIZATIONS
from app.services.tasks import card_signal
from app.services.vacancy_exam import TOPIC_LABELS

logger = logging.getLogger(__name__)


def order_pool(ids: list, scores: dict, fused: dict, best: dict, cold: set | None = None,
               tiers: dict | None = None, confirmed: dict | None = None, fits: dict | None = None,
               bands: dict | None = None) -> list:
    """Rank the whole pool, then the caller slices a page. A later page cannot reorder an earlier one.

    With tiers, the key is (−tier, −confirmed grade, −score, −fit, id): the fit decides the tier,
    and a passed test orders people inside it. Without tiers the key stays score, fused rank, LCB, id.

    `cold` holds candidates with no grade test. Each block of ten that would otherwise be all tested
    gives its last seat to the next cold candidate of the same tier, when that candidate's score
    is within 0.08. A cold candidate who already earned a seat stays there.
    """
    if bands is not None:
        # Category first, then the same key as the product order. A later class cannot pass an earlier one.
        ranked = sorted(ids, key=lambda i: (
            bands.get(i, 2), -scores[i], -fused.get(i, 0.0), -best.get(i, 0.0), str(i)))
    elif tiers is None:
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
            if bands is not None and bands.get(guest, 2) != bands.get(out[end - 1], 2):
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


def _rrf_ties(ordered_ids: list, scores: dict | None = None) -> dict:
    """Same reciprocal weight for equal scores. Without scores, position is the rank."""
    if not scores:
        return _rrf(ordered_ids)
    out: dict = {}
    rank = 0
    previous = None
    for index, pid in enumerate(ordered_ids):
        value = scores.get(pid)
        if previous is None or value != previous:
            rank = index
            previous = value
        out[pid] = 1.0 / (RRF_K + rank + 1)
    return out


# When a meaning vector exists it is 15% of the query signal. Words stay 85%.
# With the model off, or when it returns nothing, the map is the word rank alone.
RULES_SHARE = 0.85
MEANING_SHARE = 0.15


def fuse_text(lex_order: list, dense_order: list | None = None, lex_scores: dict | None = None) -> dict:
    """Reciprocal rank of the wording and, when present, a 15% share of the meaning.

    A discipline score and a test result are not arguments: growing either one cannot
    change this map, so the «Запрос» factor cannot smuggle them in. Equal word scores
    share a rank, so the factor does not depend on the candidate id. No meaning vector
    leaves the word rank exactly as it was.
    """
    lex = _rrf_ties(list(lex_order), lex_scores)
    if not dense_order:
        return lex
    fused = {pid: RULES_SHARE * weight for pid, weight in lex.items()}
    for pid, weight in _rrf(list(dense_order)).items():
        fused[pid] = fused.get(pid, 0.0) + MEANING_SHARE * weight
    return fused


def text_blend(dense_used: bool) -> str:
    return "rules+meaning" if dense_used else "rules"


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
        # SEC3-10: «tested» and «not tested» are cells too. Fewer than min_n on either side would let a
        # difference of two counts point at one or two people, so that count is not shown.
        small = tested < min_n or people - tested < min_n
        cells.append({"role": role, "grade": grade, "hidden": hidden,
                      "candidates": None if hidden else people,
                      "tested": None if hidden or small else tested})
    return cells


def assessed_card(facts) -> bool:
    """The card's category is confirmed by a test («Только грейд, подтверждённый тестом»)."""
    return facts is not None and facts.grade_source == "assessed"


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
    # An alias, so the rule also works in a query that already joins CategoryAssignment (the public
    # category ranking): without it the subquery correlates away its own FROM and the query fails.
    own = aliased(CategoryAssignment)
    graded = exists(select(own.id).where(
        own.participant_id == Participant.id,
        own.grade_source.in_(("declared", "assessed")),
    ))
    return and_(
        Participant.is_visible.is_(True),
        Participant.deleted_at.is_(None),
        Participant.suspended_at.is_(None),
        Participant.guest_until.is_(None),
        Participant.job_search != "not_looking",
        # Consent of a representative does not replace a birth date.
        Participant.birth_date.is_not(None),
        or_(adult, Participant.minor_consent_given.is_(True)),
        graded,
    )


async def searchable_count(db: AsyncSession) -> int:
    """People a search can see before a need's role, grade and skill filters."""
    return int(await db.scalar(select(func.count()).select_from(Participant).where(
        _in_search(age_confirmed_adult()))) or 0)


def visible_in_search():
    """The one "visible to an employer" rule as of now (audit-3 P1-1): search, favorites, the salary market
    and the public category ranking all use it, so an aggregate never counts someone the search would hide."""
    return _in_search(age_confirmed_adult())


async def bank_grid(db: AsyncSession) -> dict:
    """The candidate bank by specialization and grade: who is in search and how many confirmed the grade by test.

    Same visibility as the search itself, including the survey-or-test grade inside ``_in_search``.
    """
    adult = age_confirmed_adult()
    PSI = ProfileSearchIndex
    tested = func.count(Participant.assessed_grade).filter(PSI.grade == Participant.assessed_grade)
    rows = (await db.execute(
        select(PSI.role, PSI.grade, func.count(), tested)
        .join(Participant, Participant.id == PSI.participant_id)
        .where(_in_search(adult))
        .group_by(PSI.role, PSI.grade))).all()
    return {"min_cell": BANK_MIN, "cells": bank_cells([tuple(r) for r in rows])}


def passes_role_grade(primary_role: str | None, primary_grade: str | None,
                      confirmations: list[tuple[str, str]], role: str | None, grade: str | None) -> bool:
    """Who stays when the employer filters by role and grade.

    A second confirmed specialization counts for that pair. The primary grade
    alone must not hide it. A grade filter without a role still reads the primary category.
    """
    if role and grade:
        if primary_role == role and primary_grade == grade:
            return True
        return (role, grade) in confirmations
    if role:
        return primary_role == role or any(spec == role for spec, _ in confirmations)
    if grade:
        return primary_grade == grade
    return True


def _role_for_need(cat, need_role: str | None, confirmation,
                   resume=None) -> tuple[str | None, str | None, str | None]:
    """Use the confirmation that matches the need when it is not the primary category.

    Without one, an extra resume in that specialization gives a declared grade.
    """
    role = cat.primary_role if cat else None
    grade = cat.grade if cat else None
    source = cat.grade_source if cat else None
    if need_role and confirmation is not None and confirmation.specialization == need_role and role != need_role:
        return confirmation.specialization, confirmation.grade, "assessed"
    if need_role and resume is not None and resume.specialization == need_role and role != need_role:
        return resume.specialization, resume.grade, "declared"
    return role, grade, source


def visible_card(stack: list, experience, disciplines: list, why: list[str], *,
                 show_stack: bool, show_fsp: bool, show_experience: bool):
    """What the anonymous card may print. The score is computed before this and does not read it."""
    if not show_stack:
        stack = []
    if not show_experience:
        experience = None
    if not show_fsp:
        disciplines = []
        why = [line for line in why if not line.startswith(("Подтверждено ФСП", "Присвоенный разряд", "Разброс шкалы"))]
    return stack, experience, disciplines, why


def shown_region(region: str | None, show_city: bool) -> str | None:
    """The city on the anonymous card. Hiding it leaves the field empty; the score still uses the city."""
    if not show_city:
        return None
    return region or None


def shown_category(primary_role: str | None, primary_grade: str | None, primary_source: str | None,
                   scored_role: str | None, scored_grade: str | None, scored_source: str | None,
                   ) -> tuple[str | None, str | None, str | None, dict | None]:
    """The card header is the pair that entered the score. The primary pair stays beside it."""
    if scored_role and scored_role != primary_role:
        also = None
        if primary_role:
            also = {"role": primary_role, "grade": primary_grade, "grade_source": primary_source}
        return scored_role, scored_grade, scored_source, also
    return primary_role, primary_grade, primary_source, None


def _scored_roles(matches: dict, ids: list) -> dict:
    out = {}
    for pid in ids:
        row = matches.get(pid)
        facts = row.facts if row else None
        if facts and facts.role:
            out[pid] = (facts.role, facts.grade, facts.grade_source)
    return out


def _in_pairs(pairs: list[tuple[str, str]], PSI=ProfileSearchIndex):
    """In one of the specialization × grade pairs: by the search index, a test confirmation or the resume."""
    confirmed_pair = select(GradeConfirmation.participant_id).where(
        tuple_(GradeConfirmation.specialization, GradeConfirmation.grade).in_(pairs))
    resume_pair = select(CandidateResume.participant_id).where(
        tuple_(CandidateResume.specialization, CandidateResume.grade).in_(pairs),
        CandidateResume.participant_id.not_in(select(GradeConfirmation.participant_id).where(
            tuple_(GradeConfirmation.specialization, GradeConfirmation.grade).in_(pairs))))
    return or_(
        tuple_(PSI.role, PSI.grade).in_(pairs),
        Participant.id.in_(confirmed_pair),
        Participant.id.in_(resume_pair),
    )


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
    city: str | None = None,
    work_format: str | None = None,
    need: NeedSpec | None = None,
    employer_id: uuid.UUID | None = None,
    build_cards: bool = True,
    grade_span: str = "near",
) -> dict:
    wanted = {n for s in (skills or []) if (n := normalize_skill(s))}
    if q:
        wanted |= {e.skill for e in extract_skills(q)}
    wanted_list = sorted(wanted)

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

    adult = age_confirmed_adult()
    stmt = (select(Participant.id, lex)
            .join(PSI, PSI.participant_id == Participant.id)
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
    # City and format are score factors. A mismatch stays in the list and sorts lower.
    span = grade_span if grade_span in ("exact", "near", "wide", "plus_minus", "any") else "near"
    pairs = category_pairs(role, grade, span) if role and grade else None
    if pairs:
        stmt = stmt.where(_in_pairs(pairs, PSI))
    elif role:
        confirmed_here = select(GradeConfirmation.participant_id).where(
            GradeConfirmation.specialization == role)
        resume_here = select(CandidateResume.participant_id).where(CandidateResume.specialization == role)
        stmt = stmt.where(or_(PSI.role == role, Participant.id.in_(confirmed_here), Participant.id.in_(resume_here)))
    elif grade:
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
    stmt = stmt.order_by(lex.desc(), Participant.id).limit(POOL_LIMIT)
    rows = (await db.execute(stmt)).all()

    ids_set: set[uuid.UUID] = {r.id for r in rows}
    lex_of = {r.id: float(r.lex or 0.0) for r in rows}
    lex_order = sorted(lex_of, key=lambda i: (-lex_of[i], str(i)))

    dense_hit: set = set()
    dense_order: list = []
    if q and embeddings_enabled():
        vec = await embed(q)
        if vec is not None:
            dense_order = list(await db.scalars(
                select(ProfileEmbedding.participant_id)
                .join(Participant, Participant.id == ProfileEmbedding.participant_id)
                .where(_in_search(adult))
                .order_by(ProfileEmbedding.embedding.cosine_distance(vec))
                .limit(DENSE_POOL)
            ))
            dense_hit = set(dense_order[:20])
            ids_set.update(dense_order)

    if employer_id is not None and ids_set:
        from app.services.exclusions import drop_refused
        gone = await drop_refused(db, ids_set, employer_id, need.industry if need else None)
        ids_set -= gone
        lex_order = [i for i in lex_order if i not in gone]
        dense_order = [i for i in dense_order if i not in gone]

    by_discipline: dict[uuid.UUID, dict[str, float]] = {}
    if ids_set:
        for pid, disc, value in await db.execute(
                select(DisciplineScore.participant_id, DisciplineScore.discipline, DisciplineScore.lcb).where(
                    DisciplineScore.participant_id.in_(list(ids_set)))):
            by_discipline.setdefault(pid, {})[disc] = float(value or 0.0)

    need = need or NeedSpec(role=role, grade=grade, skills=tuple(wanted_list), text=bool(q),
                            city=city, work_format=work_format)
    if q:
        need = NeedSpec(
            role=need.role, grade=need.grade, skills=need.skills, nice=need.nice,
            industry=need.industry, text=True, salary_from=need.salary_from, salary_to=need.salary_to,
            city=city or need.city, work_format=work_format or need.work_format)
    elif city or work_format:
        need = NeedSpec(
            role=need.role, grade=need.grade, skills=need.skills, nice=need.nice,
            industry=need.industry, text=need.text, salary_from=need.salary_from, salary_to=need.salary_to,
            city=city or need.city, work_format=work_format or need.work_format)

    def _need_lcb(pid: uuid.UUID) -> float:
        return lcb_for_need(need.role, by_discipline.get(pid, {}), discipline)[0]

    best = {pid: _need_lcb(pid) for pid in ids_set}
    # Words and meaning only. The test and the FSP axis stay out of the «Запрос» factor.
    text_fused = fuse_text(lex_order, dense_order or None, lex_of)
    pair_order = None
    if q and cross_enabled() and ids_set:
        head = sorted(
            (pid for pid in text_fused if pid in ids_set),
            key=lambda pid: (-text_fused[pid], str(pid)),
        )[:RERANK_HEAD]
        if not head:
            head = sorted(ids_set, key=str)[:RERANK_HEAD]
        found = (await db.execute(
            select(ProfileSearchIndex.participant_id, ProfileSearchIndex.skills_text)
            .where(ProfileSearchIndex.participant_id.in_(head)))).all()
        pair_order = await asyncio.to_thread(rank_pairs, found, q)
    text_fused = rerank_text(text_fused, pair_order)

    # Sort ties still see the test and the discipline rule. The FSP list uses the need's
    # discipline, not the highest result in any sport.
    fused: dict[uuid.UUID, float] = {pid: 0.0 for pid in ids_set}
    sort_rankings: list[list] = [
        sorted(ids_set, key=lambda i: (-best[i], str(i))),
        lex_order,
    ]
    if dense_order:
        sort_rankings.append(dense_order)

    # theta is on one IRT scale, so the best completed primary test is comparable.
    # A vacancy test is practice. A jury trial must not move the ranking.
    not_trial = or_(TestSession.flags["mode"].astext.is_(None), TestSession.flags["mode"].astext != "express")
    if ids_set:
        test_theta: dict[uuid.UUID, float] = {
            pid: theta for pid, theta in await db.execute(
                select(TestSession.participant_id, func.max(TestSession.irt_theta))
                .where(TestSession.participant_id.in_(list(ids_set)), TestSession.status == "completed",
                       TestSession.irt_theta.is_not(None), not_trial, ~TestSession.flags.has_key("vacancy_id"))
                .group_by(TestSession.participant_id))
        }
        if test_theta:
            sort_rankings.append(sorted(test_theta, key=lambda i: -test_theta[i]))

    for ranking in sort_rankings:
        for pid, weight in _rrf(ranking).items():
            if pid in fused:
                fused[pid] += weight

    all_ids = list(ids_set)
    have: dict[uuid.UUID, set[str]] = {}
    if wanted:
        for pid, name in await db.execute(
                select(Skill.participant_id, Skill.name).where(
                    Skill.participant_id.in_(all_ids), Skill.confirmed.is_(True), Skill.name.in_(wanted))):
            have.setdefault(pid, set()).add(name)

    matches = await score_pool(
        db, all_ids, need, text_fused, discipline, employer_id, by_discipline=by_discipline)
    platform_held = 0
    full_card = True
    if employer_id is not None:
        company = await db.get(Employer, employer_id)
        if company is not None and not sees_senior(company.hiring_practice):
            full_card = False
            kept = []
            for pid in all_ids:
                person = matches[pid].facts
                if person and person.grade in ("senior", "lead") and person.grade_source == "assessed":
                    platform_held += 1
                else:
                    kept.append(pid)
            all_ids = kept
    if assessed_only:
        # ST-09: the SQL filter keeps anyone with a test on any specialization (Participant.assessed_grade),
        # and dense hits skip it. The card shows the source of the scored category, so the filter does too.
        all_ids = [i for i in all_ids if assessed_card(matches[i].facts)]
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
    plain = order_pool(
        all_ids, score_of, fused, best, None,
        tiers={i: matches[i].tier or 0 for i in all_ids} if matching_service.USE_FIT_TIERS else None,
        confirmed={i: matches[i].confirmed for i in all_ids} if matching_service.USE_FIT_TIERS else None,
        fits={i: matches[i].fit or 0.0 for i in all_ids} if matching_service.USE_FIT_TIERS else None)
    cold_seats = {pid for pid, was in zip(ordered, plain, strict=True) if pid in cold and pid != was}
    # Audit-5 A2: with a grade the default span also keeps the neighbour grade and role, so a stricter
    # filter can list more people than the role alone. The header says how many sit in the asked pair.
    in_category = None
    if role and grade and all_ids:
        in_category = int(await db.scalar(
            select(func.count()).select_from(Participant)
            .join(ProfileSearchIndex, ProfileSearchIndex.participant_id == Participant.id)
            .where(Participant.id.in_(all_ids), _in_pairs([(role, grade)]))) or 0)
    elif role and grade:
        in_category = 0
    # DoR-10 / V-SOTA-08: the asked pair is one bank cell. A count of 1–4 is the number the bank hides,
    # so it is not printed here either (k-anonymity, BANK_MIN). Zero says nothing about a person.
    in_category_hidden = in_category is not None and 0 < in_category < BANK_MIN
    if in_category_hidden:
        in_category = None
    categories = recommended_categories(
        [(f.role, f.grade, matches[i].score) for i in ordered[:200] if (f := matches[i].facts)],
        min_n=BANK_MIN)
    header = {"total": len(all_ids), "pool_capped": len(rows) >= POOL_LIMIT, "query_skills": wanted_list,
              "recommended_categories": categories, "pay_hint": pay_hint, "skill_hint": skill_hint,
              "text_blend": text_blend(bool(dense_order)), "pair_device": pair_device(),
              "platform_held": platform_held, "in_category": in_category,
              "in_category_hidden": in_category_hidden}
    if not build_cards:
        # The cache keeps the order and the scores. Cards for one page are built later.
        items = []
        for pid in ordered[:limit]:
            m = matches[pid]
            facts = m.facts
            items.append({
                "candidate_id": str(pid),
                "have": sorted(have.get(pid, ())),
                "skill_evidence": dict(facts.skills) if facts else {},
                "scored_role": facts.role if facts else None,
                "scored_grade": facts.grade if facts else None,
                "scored_source": facts.grade_source if facts else None,
                "match": _match_body(m, pid in cold_seats),
            })
        return {**header, "items": items}
    ordered = ordered[offset:offset + limit]
    chosen = {
        pid: (matches[pid].facts.fsp_lcb, matches[pid].facts.fsp_kind, matches[pid].facts.fsp_discipline)
        for pid in ordered if matches.get(pid) and matches[pid].facts
    }
    cards = await _build_cards(
        db, ordered, wanted, have, dense_hit, discipline, chosen, _scored_roles(matches, ordered),
        full_card=full_card)
    for card in cards:
        m = matches[uuid.UUID(card["candidate_id"])]
        card["match"] = _match_body(m, uuid.UUID(card["candidate_id"]) in cold_seats)
        if not full_card:
            card["match"]["info"] = [line for line in card["match"]["info"] if "признаков роста" not in line]
        card["skill_evidence"] = dict(m.facts.skills) if m.facts else {}
    return {"total": len(all_ids), "pool_capped": len(rows) >= POOL_LIMIT, "query_skills": wanted_list,
            "recommended_categories": categories, "pay_hint": pay_hint, "skill_hint": skill_hint,
            "text_blend": text_blend(bool(dense_order)), "pair_device": pair_device(),
            "platform_held": platform_held, "in_category": in_category,
            "in_category_hidden": in_category_hidden, "items": cards}


def _match_body(m: PoolMatch, cold_seat: bool) -> dict:
    reasons = [{"code": r.code, "text": r.text, "tone": r.tone,
                "source": reason_source(r.code), "points": r.points} for r in (m.reasons or [])]
    if cold_seat:
        reasons.append({
            "code": "COLD_SEAT",
            "text": "Место для кандидата без теста (правило разнообразия)",
            "tone": "info", "source": None, "points": None,
        })
    return {
        "score": m.score, "basis": m.basis, "plus": m.plus, "minus": m.minus, "info": m.info,
        "employer": m.employer, "accept": m.accept, "congestion": m.congestion,
        "reply": m.reply, "mutual": m.mutual, "rejected_by": list(m.rejected_by or []),
        "reasons": reasons,
        "factors": [{"key": f.key, "label": f.label, "weight": f.weight, "value": f.value,
                     "contrib": f.contrib} for f in m.factors],
    }


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
    employer: float = 0.0
    accept: float | None = None
    congestion: float = 0.0
    reply: dict | None = None
    mutual: float | None = None
    rejected_by: list | None = None


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


async def score_pool(db: AsyncSession, ids: list[uuid.UUID], need: NeedSpec, text_fused: dict[uuid.UUID, float],
                     discipline: str | None = None, employer_id: uuid.UUID | None = None,
                     by_discipline: dict[uuid.UUID, dict[str, float]] | None = None) -> dict[uuid.UUID, PoolMatch]:
    """Load the facts the factor score needs. ``text_fused`` is words and meaning only."""
    if not ids:
        return {}
    names = set(need.skills) | set(need.nice)
    for group in RELATED:
        if names & group:
            names |= group
    skills: dict[uuid.UUID, dict[str, str]] = {}
    checked: dict[uuid.UUID, set[str]] = {}
    if names:
        for pid, name, trust, items in await db.execute(
                select(Skill.participant_id, Skill.name, Skill.trust_level, Skill.test_items).where(
                    Skill.participant_id.in_(ids), Skill.confirmed.is_(True), Skill.name.in_(names))):
            skills.setdefault(pid, {})[name] = trust
            if items:
                checked.setdefault(pid, set()).add(name)
    people = {p.id: p for p in await db.scalars(select(Participant).where(Participant.id.in_(ids)))}
    cats = {c.participant_id: c for c in await db.scalars(
        select(CategoryAssignment).where(CategoryAssignment.participant_id.in_(ids)))}
    if by_discipline is None:
        by_discipline = {}
        for pid, disc, value in await db.execute(
                select(DisciplineScore.participant_id, DisciplineScore.discipline, DisciplineScore.lcb).where(
                    DisciplineScore.participant_id.in_(ids))):
            by_discipline.setdefault(pid, {})[disc] = float(value or 0.0)
    confs = {(c.participant_id, c.specialization): c for c in await db.scalars(
        select(GradeConfirmation).where(GradeConfirmation.participant_id.in_(ids)))}
    extra = {(r.participant_id, r.specialization): r for r in await db.scalars(
        select(CandidateResume).where(CandidateResume.participant_id.in_(ids)))} if need.role else {}
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
    top = max(text_fused.values(), default=0.0) or 1.0
    marks: dict[uuid.UUID, dict] = {}
    failed_targets: dict[tuple, str] = {}
    if ids:
        mark_rows = (await db.execute(
            select(TestSession.participant_id, TestSession.flags, TestSession.specialization,
                   TestSession.target_grade)
            .where(TestSession.participant_id.in_(list(ids)), TestSession.status == "completed",
                   TestSession.completed_at.is_not(None))
            .order_by(TestSession.completed_at.desc()))).all()
        marks = latest_grade_flags([(pid, flags) for pid, flags, _, _ in mark_rows])
        # DoR-N7: a failed test at the shown, unconfirmed grade lowers the grade the need-fit reads.
        failed_targets = latest_failed_targets(
            [(pid, spec, target, flags) for pid, flags, spec, target in mark_rows])
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
        role_name, grade_name, grade_source = _role_for_need(cat, need.role, conf, extra.get((pid, need.role)))
        facts = CandidateFacts(
            role=role_name, grade=grade_name,
            grade_source=grade_source, skills=skills.get(pid, {}),
            # A legacy confirmation without a probability counts as a bare pass, not as certainty (audit-4 F-2).
            test_p=conf.p_pass if conf and conf.p_pass is not None else (PASS_P if conf else None),
            test_spec=conf.specialization if conf else None,
            fsp_lcb=fsp_lcb, fsp_kind=fsp_kind, fsp_discipline=fsp_discipline,
            industry=p.industry if p else None,
            text_rank=text_fused.get(pid, 0.0) / top,
            salary_from=p.salary_from_gross if p else None, salary_to=p.salary_to_gross if p else None,
            test_se=conf.se if conf and conf.se else None,
            test_correct=counts.get(conf.session_id, (None, None))[0] if conf and conf.session_id else None,
            test_n=counts.get(conf.session_id, (None, None))[1] if conf and conf.session_id else None,
            open_invites=int(pending.get(pid, 0)),
            salary_refusals=int(refusals.get(pid, 0)),
            job_search=(p.job_search if p else None) or "open",
            interview_outcome=interviews.get(pid),
            city=p.region if p and bool(getattr(p, "show_city", True)) else None,
            work_formats=tuple(p.work_formats or ()) if p else (),
            tested_at=conf.confirmed_at if conf else None,
            failed_grade=failed_targets.get((pid, role_name)) if role_name else None,
            tested_skills=frozenset(checked.get(pid, ())),
        )
        m = match_score(need, facts)
        adjusted, note = penalised(m.score, marks.get(pid))
        if note:
            m.score = adjusted
            m.info.append(note)
        growth = ambition_note(facts.grade, facts.job_search, facts.skills, p.work_goal if p else None)
        if growth:
            m.info.append(growth)
        out[pid] = PoolMatch(m.score, m.factors, m.plus, m.minus, m.info, facts, m.basis, m.reasons,
                             m.fit, m.tier, m.confirmed, m.employer, m.accept, m.congestion,
                             reply_outlook(need, facts), m.mutual, list(m.rejected_by or []))
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
                out[pid] = standing_line(pct, label)
    return out


# Method behind each confirmed trust level. Bump the tag when the method changes.
SKILL_METHODS = {"test_confirmed": "test/cat-3pl", "resume_confirmed": "resume-quote/2026-10"}


async def _build_cards(db, ordered, wanted, have, dense_hit, discipline_filter,
                       fsp_choice: dict | None = None, scored: dict | None = None,
                       full_card: bool = True) -> list[dict]:
    parts = {p.id: p for p in await db.scalars(select(Participant).where(Participant.id.in_(ordered)))}
    cats = {c.participant_id: c for c in await db.scalars(
        select(CategoryAssignment).where(CategoryAssignment.participant_id.in_(ordered)))}
    # Where each confirmed skill comes from, when, and by which method (competitor idea 5). Self-reported
    # skills have no entry: nothing confirmed them.
    provenance: dict = {}
    for sk in await db.scalars(select(Skill).where(Skill.participant_id.in_(ordered),
                                                   Skill.trust_level.in_(tuple(SKILL_METHODS)))):
        when = sk.confirmed_at or sk.created_at
        provenance.setdefault(sk.participant_id, {})[sk.name] = {
            "source": sk.trust_level, "verified_at": when.date().isoformat() if when else None,
            "method_version": SKILL_METHODS[sk.trust_level]}
    # NEW-2: a test decision within one SE of the cut is shown as "on the border", not hidden.
    borderline: set = set()
    for c in await db.scalars(select(GradeConfirmation).where(GradeConfirmation.participant_id.in_(ordered))):
        cat_c = cats.get(c.participant_id)
        if (cat_c and cat_c.grade_source == "assessed" and c.specialization == cat_c.primary_role
                and c.grade == cat_c.grade and is_borderline(c.theta, c.se, c.grade)):
            borderline.add(c.participant_id)
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
    resumes = {(r.participant_id, r.specialization): r for r in await db.scalars(
        select(CandidateResume).where(CandidateResume.participant_id.in_(ordered)))} if scored else {}

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
                                "score": ds.score, "sigma": ds.sigma, "lcb": ds.lcb, "confidence": ds.confidence,
                                "best_rank": ds.best_rank,
                                "rank_assigned_at": ds.rank_assigned_at.isoformat() if ds.rank_assigned_at else None,
                                "rank_order_ref": ds.rank_order_ref,
                                "events_count": ds.events_count, "evidence": evidence})
        header_role = cat.primary_role if cat else None
        header_grade = cat.grade if cat else None
        header_source = cat.grade_source if cat else None
        row = (scored or {}).get(pid)
        header_role, header_grade, header_source, also_primary = shown_category(
            header_role, header_grade, header_source,
            row[0] if row else None, row[1] if row else None, row[2] if row else None)
        resume = resumes.get((pid, header_role)) if also_primary else None
        if resume is not None and header_source == "declared":
            why.append(f"Дополнительное резюме: {header_role}, {header_grade}, грейд заявлен")
        if header_source == "assessed" and header_grade:
            why.append(f"Грейд {header_grade} подтверждён тестом")
        if also_primary and also_primary.get("role"):
            state = "подтверждена тестом" if also_primary.get("grade_source") == "assessed" else "не подтверждена"
            why.append(f"Основная категория: {also_primary['role']}, {also_primary['grade']}, {state}")
        if disciplines:
            picked = (fsp_choice or {}).get(pid)
            if discipline_filter:
                top = next((d for d in disciplines if d["discipline"] == discipline_filter), disciplines[0])
                shown, weight_note = top["lcb"], ""
            elif picked and picked[2]:
                top = next((d for d in disciplines if d["discipline"] == picked[2]), disciplines[0])
                shown = picked[0] if picked[0] is not None else top["lcb"]
                weight_note = " (учтено с весом 0,5)" if picked[1] == "other" else ""
            else:
                top = disciplines[0]
                shown, weight_note = top["lcb"], ""
            if top["best_rank"]:
                why.append(f"Присвоенный разряд {top['best_rank']} ({top['label']})")
            shown_text = f"{float(shown):.2f}".replace(".", ",")
            why.append(
                f"Подтверждено ФСП: {top['label']}, нижняя граница {shown_text}{weight_note}, "
                f"уверенность {round(top['confidence'] * 100)}%, событий {top['events_count']}")
            span = elo_stretch(float(top["score"]), float(top.get("sigma") or 0))
            center = f"{span['mu']:.2f}".replace(".", ",")
            width = f"{span['sigma']:.2f}".replace(".", ",")
            why.append(
                f"Разброс шкалы {center} ± {width}, по {top['events_count']} событиям. "
                "В балле остаётся нижняя граница.")
            # The header and the evidence list follow the discipline that entered the score,
            # not the highest lower bound in some other sport.
            disciplines = [top] + [row for row in disciplines if row is not top]
        if pid in dense_hit:
            why.append("Смысловое совпадение с запросом")
        if p.practice_at is not None and p.practice_topic:
            mark = "верно" if p.practice_ok else "с ошибкой"
            topic = TOPIC_LABELS.get(p.practice_topic, p.practice_topic)
            why.append(f"Короткая практика ({topic}): {mark}, {days_ago(p.practice_at)}")
        if task_line := card_signal(p, days_ago):
            why.append(task_line)
        if full_card and (code_line := code_profile_line(getattr(p, "github", None))):
            why.append(code_line)
        line = percentiles.get(pid)
        if line:
            why.append(line)
        stack = list(resume.stack or []) if resume is not None else (list(cat.stack) if cat else [])
        show_city = bool(p.show_city) and full_card
        show_fsp = bool(getattr(p, "show_fsp", True)) and full_card
        show_experience = bool(getattr(p, "show_experience", True)) and full_card
        stack, experience, disciplines, why = visible_card(
            stack, p.experience_years, disciplines, why,
            show_stack=bool(getattr(p, "show_stack", True)),
            show_fsp=show_fsp,
            show_experience=show_experience)
        cards.append({
            "candidate_id": str(pid),
            "role": header_role,
            "grade": header_grade,
            "grade_source": header_source,
            "grade_borderline": pid in borderline,
            "skill_provenance": provenance.get(pid, {}),
            "also_primary": also_primary,
            "region": shown_region(p.region, show_city),
            "experience_years": experience,
            "soft_skills": list(getattr(p, "soft_skills", None) or []) if full_card else [],
            "stack": stack,
            "resume_summary": resume.summary if resume is not None and full_card else None,
            "matched_skills": matched,
            "missing_skills": sorted(wanted - set(matched)),
            "disciplines": disciplines,
            "why": why,
        })
    return cards
