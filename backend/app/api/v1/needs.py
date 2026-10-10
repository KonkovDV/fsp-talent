"""Employer needs: versioned search profiles, matches with explanations, recommended categories, shortlist."""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.core.redis_client import get_redis
from app.models import (
    CategoryAssignment,
    GradeConfirmation,
    InterviewSlot,
    Need,
    NeedHidden,
    NeedShortlist,
    NeedVersion,
    Offer,
    Participant,
)
from app.services.ai import providers, second_opinion
from app.services.cities import CITIES
from app.services.matching import NeedSpec, anonymous_compare
from app.services.need_draft import draft_need
from app.services.search import cache as shortlist_cache
from app.services.search.pipeline import _build_cards, score_pool, search_candidates, searchable_count, shown_category
from app.services.skills import normalize_skill
from app.services.survey import INDUSTRIES, SPECIALIZATIONS
from app.services.vacancy_exam import form_exam

router = APIRouter(prefix="/needs", tags=["needs"])
logger = logging.getLogger(__name__)
Grade = Literal["intern", "junior", "middle", "senior", "lead"]


class NeedParams(BaseModel):
    role: str | None = None
    grade: Grade | None = None
    skills: list[str] = Field(default_factory=list, max_length=15)
    nice_to_have: list[str] = Field(default_factory=list, max_length=15)
    industry: str | None = None
    work_goal: Literal["job", "internship"] | None = None
    has_fsp: bool | None = None
    salary_from: int | None = Field(None, ge=0)
    salary_to: int | None = Field(None, ge=0)
    city: str | None = None
    work_format: Literal["office", "hybrid", "remote"] | None = None
    q: str | None = Field(None, max_length=300)

    @model_validator(mode="after")
    def _check(self):
        if self.role and self.role not in SPECIALIZATIONS:
            raise ValueError("Неизвестная специализация")
        if self.industry and self.industry not in INDUSTRIES:
            raise ValueError("Неизвестная сфера")
        if self.city and self.city not in CITIES:
            raise ValueError("Неизвестный город")
        if self.salary_from and self.salary_to and self.salary_from > self.salary_to:
            raise ValueError("Зарплата «от» больше, чем «до»")
        self.skills = sorted({n for s in self.skills if (n := normalize_skill(s))})
        self.nice_to_have = sorted({n for s in self.nice_to_have if (n := normalize_skill(s))} - set(self.skills))
        return self

    def spec(self) -> NeedSpec:
        return NeedSpec(
            role=self.role, grade=self.grade, skills=tuple(self.skills), nice=tuple(self.nice_to_have),
            industry=self.industry, text=bool(self.q), salary_from=self.salary_from, salary_to=self.salary_to,
            city=self.city, work_format=self.work_format)


class NeedIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    params: NeedParams
    expected_version: int | None = Field(None, ge=1)


async def _own(db: AsyncSession, need_id: uuid.UUID, current: dict) -> Need:
    need = await db.get(Need, need_id)
    if need is None or need.employer_id != uuid.UUID(current["sub"]):
        raise ApiError(404, "need_not_found")
    return need


async def _params(db: AsyncSession, need: Need, version: int | None = None) -> NeedVersion:
    row = await db.scalar(select(NeedVersion).where(NeedVersion.need_id == need.id,
                                                    NeedVersion.version == (version or need.version)))
    if row is None:
        raise ApiError(404, "need_not_found", "Нет такой версии потребности")
    return row


def _out(need: Need, ver: NeedVersion, shortlist: int = 0) -> dict:
    return {"id": str(need.id), "title": need.title, "version": need.version, "archived": need.archived,
            "params": ver.params, "shortlist_count": shortlist, "updated_at": need.updated_at.isoformat()}


class DraftIn(BaseModel):
    text: str = Field(min_length=10, max_length=8000)


@router.post("/draft")
async def draft(body: DraftIn, current: dict = Depends(get_current_employer)):
    """Fill a need from pasted text. Nothing is saved and nothing is fetched from a job board."""
    if await too_many(f"need-draft:{current['sub']}", 20, 3600):
        raise ApiError(429, "rate_limited", "Слишком часто. Подождите немного.")
    return draft_need(body.text)


@router.post("", status_code=201)
async def create_need(body: NeedIn, current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    need = Need(employer_id=uuid.UUID(current["sub"]), title=body.title, version=1)
    db.add(need)
    await db.flush()
    ver = NeedVersion(need_id=need.id, version=1, params=body.params.model_dump())
    db.add(ver)
    await db.commit()
    return _out(need, ver)


@router.get("")
async def list_needs(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    needs = list(await db.scalars(select(Need).where(Need.employer_id == uuid.UUID(current["sub"]),
                                                     Need.archived.is_(False)).order_by(Need.updated_at.desc())))
    if not needs:
        return []
    ids = [need.id for need in needs]
    counts = {need_id: count for need_id, count in (await db.execute(
        select(NeedShortlist.need_id, func.count()).where(NeedShortlist.need_id.in_(ids))
        .group_by(NeedShortlist.need_id))).all()}
    versions = {(row.need_id, row.version): row for row in await db.scalars(
        select(NeedVersion).where(NeedVersion.need_id.in_(ids)))}
    out = []
    for need in needs:
        ver = versions.get((need.id, need.version))
        if ver is None:
            raise ApiError(404, "need_not_found", "Нет такой версии потребности")
        out.append(_out(need, ver, int(counts.get(need.id, 0))))
    return out


@router.get("/{need_id}")
async def get_need(need_id: uuid.UUID, current: dict = Depends(get_current_employer),
                   db: AsyncSession = Depends(get_db)):
    need = await _own(db, need_id, current)
    versions = list(await db.scalars(select(NeedVersion).where(NeedVersion.need_id == need.id)
                                     .order_by(NeedVersion.version.desc())))
    return {**_out(need, versions[0]), "versions": [
        {"version": v.version, "params": v.params, "created_at": v.created_at.isoformat()} for v in versions]}


@router.put("/{need_id}")
async def update_need(need_id: uuid.UUID, body: NeedIn, current: dict = Depends(get_current_employer),
                      db: AsyncSession = Depends(get_db)):
    """An edit is a new version; earlier versions and shortlist decisions stay as they were."""
    need = await db.get(Need, need_id, with_for_update=True)
    if need is None or need.employer_id != uuid.UUID(current["sub"]):
        raise ApiError(404, "need_not_found")
    if body.expected_version is not None and body.expected_version != need.version:
        raise ApiError(409, "conflict", "Потребность уже изменилась. Обновите страницу.")
    need.version += 1
    need.title = body.title
    need.updated_at = datetime.now(UTC)
    ver = NeedVersion(need_id=need.id, version=need.version, params=body.params.model_dump())
    db.add(ver)
    await db.commit()
    return _out(need, ver)


@router.post("/{need_id}/versions/{version}/restore")
async def restore_need(need_id: uuid.UUID, version: int, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    """Copy an older version into a new one. The shortlist stays; nothing is rewritten in place."""
    need = await db.get(Need, need_id, with_for_update=True)
    if need is None or need.employer_id != uuid.UUID(current["sub"]):
        raise ApiError(404, "need_not_found")
    old = await _params(db, need, version)
    need.version += 1
    need.updated_at = datetime.now(UTC)
    ver = NeedVersion(need_id=need.id, version=need.version, params=dict(old.params))
    db.add(ver)
    await db.commit()
    return _out(need, ver)


@router.delete("/{need_id}")
async def archive_need(need_id: uuid.UUID, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    need = await _own(db, need_id, current)
    need.archived = True
    await db.commit()
    return {"archived": True}


async def _redis():
    try:
        return await get_redis()
    except Exception:
        return None


async def _employer_met_someone(db: AsyncSession, employer_id: uuid.UUID) -> bool:
    """An interview outcome changes this company's order, so that ranking is not shared."""
    row = await db.scalar(
        select(InterviewSlot.id)
        .join(Offer, Offer.id == InterviewSlot.offer_id)
        .where(Offer.employer_id == employer_id, InterviewSlot.outcome.is_not(None))
        .limit(1))
    return row is not None


async def _cached_page(redis, key: str, offset: int, limit: int) -> dict | None:
    if redis is None:
        return None
    try:
        stored = await shortlist_cache.read_ranked(redis, key)
    except Exception:
        return None
    if not stored:
        return None
    return shortlist_cache.slice_ranked(stored, offset, limit)


async def _matches_cached(db: AsyncSession, need: Need, params: NeedParams, limit: int, offset: int) -> dict:
    """One ranking per need version and bank epoch. Identical needs share the computation."""
    redis = await _redis()
    epoch = 0
    if redis is not None:
        try:
            epoch = await shortlist_cache.bank_epoch(redis)
        except Exception:
            redis = None
    key = shortlist_cache.shortlist_key(need.id, need.version, epoch)
    shared = shortlist_cache.shared_key(params.model_dump(), epoch)
    page = await _cached_page(redis, key, offset, limit)
    if page is not None:
        return page
    own = await _employer_met_someone(db, need.employer_id)
    if not own:
        page = await _cached_page(redis, shared, offset, limit)
        if page is not None:
            return page
    if redis is not None and not own:
        try:
            got = await redis.set(shared + ":lock", "1", nx=True, ex=20)
        except Exception:
            got = True
        if not got:
            waited = await shortlist_cache.wait_ranked(redis, shared)
            page = shortlist_cache.slice_ranked(waited, offset, limit) if waited else None
            if page is not None:
                return page
    result = await search_candidates(
        db, skills=params.skills, q=params.q, limit=shortlist_cache.WINDOW, offset=0, has_fsp=params.has_fsp,
        work_goal=params.work_goal, need=params.spec(), employer_id=need.employer_id if own else None,
        build_cards=False)
    payload = shortlist_cache.store_payload(result)
    if redis is not None:
        try:
            await shortlist_cache.write_ranked(redis, key, payload)
            if not own:
                await shortlist_cache.write_ranked(redis, shared, payload)
        except Exception:
            pass
    page = shortlist_cache.slice_ranked(payload, offset, limit)
    if page is None:
        page = shortlist_cache.slice_ranked({**payload, "complete": True}, offset, limit)
    return page or {"items": []}


async def _company_offers(db: AsyncSession, employer_id: uuid.UUID, ids: list[uuid.UUID]) -> dict[str, dict]:
    """Invitations and closed contacts of this company only."""
    if not ids:
        return {}
    found: dict[str, dict] = {}
    rows = await db.execute(
        select(Offer.candidate_id, Offer.status, Offer.contacts_revoked_at)
        .where(Offer.employer_id == employer_id, Offer.candidate_id.in_(ids)))
    for pid, status, revoked in rows:
        key = str(pid)
        prev = found.get(key) or {"invited": False, "contacts_closed": False}
        found[key] = {
            "invited": prev["invited"] or status in ("pending", "accepted"),
            "contacts_closed": prev["contacts_closed"] or revoked is not None,
        }
    return found


async def _hydrate(db: AsyncSession, page: dict) -> dict:
    """Turn a cached ranking into cards for this page only."""
    items = page.get("items") or []
    if not items or "have" not in items[0]:
        return page
    ordered = []
    have: dict[uuid.UUID, set[str]] = {}
    scored: dict[uuid.UUID, tuple] = {}
    for item in items:
        try:
            pid = uuid.UUID(item["candidate_id"])
        except (ValueError, KeyError):
            continue
        ordered.append(pid)
        have[pid] = set(item.get("have") or [])
        if item.get("scored_role"):
            scored[pid] = (item.get("scored_role"), item.get("scored_grade"), item.get("scored_source"))
    cards = await _build_cards(db, ordered, set(page.get("query_skills") or []), have, set(), None, None, scored)
    by_id = {card["candidate_id"]: card for card in cards}
    merged = []
    for item in items:
        card = by_id.get(item["candidate_id"])
        if card is None:
            continue
        card["match"] = item.get("match")
        card["skill_evidence"] = item.get("skill_evidence") or {}
        merged.append(card)
    page["items"] = merged
    return page


def visible_page(items: list[dict], hidden: set[str], offset: int, limit: int, *, show: bool) -> tuple[list[dict], int]:
    """Drop hidden cards, then page. The ranking itself is shared; hiding belongs to one company."""
    marked = [{**item, "hidden": item.get("candidate_id") in hidden} for item in items]
    shown = marked if show else [item for item in marked if not item["hidden"]]
    return shown[offset:offset + limit], len(shown)


@router.get("/{need_id}/matches")
async def matches(need_id: uuid.UUID, limit: int = Query(20, ge=1, le=50),
                  offset: int = Query(0, ge=0, le=200),
                  show_hidden: bool = Query(False),
                  current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Candidates for the need, ordered by the explainable score; role and grade are soft (neighbours count)."""
    if await too_many(f"search:candidates:{current['sub']}", limit=30, window_seconds=60):
        raise ApiError(429, "rate_limited")
    need = await _own(db, need_id, current)
    p = NeedParams(**(await _params(db, need)).params)
    ranked = await _matches_cached(db, need, p, shortlist_cache.WINDOW, 0)
    hidden = {str(pid) for pid in await db.scalars(
        select(NeedHidden.participant_id).where(NeedHidden.need_id == need.id))}
    page_items, total = visible_page(ranked.get("items") or [], hidden, offset, limit, show=show_hidden)
    result = await _hydrate(db, {**ranked, "items": page_items, "total": total})
    listed = {str(pid) for pid in await db.scalars(
        select(NeedShortlist.participant_id).where(NeedShortlist.need_id == need.id))}
    ids = []
    for card in result["items"]:
        try:
            ids.append(uuid.UUID(card["candidate_id"]))
        except (ValueError, KeyError):
            continue
    offers = await _company_offers(db, need.employer_id, ids)
    shortlist_cache.apply_company_marks(result["items"], listed, offers)
    return {**result, "need": _out(need, await _params(db, need)),
            "base_total": await searchable_count(db),
            "hidden_count": len(hidden), "ai_note": await providers.refresh(db) is not None}


@router.put("/{need_id}/hidden/{candidate_id}")
async def hide_candidate(need_id: uuid.UUID, candidate_id: uuid.UUID,
                         current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Hide one card from this need. A later version of the need keeps the hide."""
    need = await _own(db, need_id, current)
    person = await db.get(Participant, candidate_id)
    if person is None or not person.discoverable:
        raise ApiError(404, "not_found", "Кандидат не найден")
    row = await db.scalar(select(NeedHidden).where(NeedHidden.need_id == need.id,
                                                   NeedHidden.participant_id == candidate_id))
    if row is None:
        db.add(NeedHidden(need_id=need.id, participant_id=candidate_id, version=need.version))
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise ApiError(409, "conflict") from e
    return {"candidate_id": str(candidate_id), "hidden": True}


@router.delete("/{need_id}/hidden/{candidate_id}")
async def unhide_candidate(need_id: uuid.UUID, candidate_id: uuid.UUID,
                           current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    need = await _own(db, need_id, current)
    await db.execute(delete(NeedHidden).where(NeedHidden.need_id == need.id,
                                              NeedHidden.participant_id == candidate_id))
    await db.commit()
    return {"candidate_id": str(candidate_id), "hidden": False}


@router.get("/{need_id}/exam")
async def exam_preview(need_id: uuid.UUID, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    """The grade test this need would form: topic mix from its skills and text, three samples, no answer keys."""
    need = await _own(db, need_id, current)
    p = NeedParams(**(await _params(db, need)).params)
    exam = form_exam(need.title, p.q or "", [*p.skills, *p.nice_to_have], p.role, p.grade)
    exam.pop("topic_shares", None)
    return exam


@router.get("/{need_id}/compare")
async def compare(need_id: uuid.UUID, ids: str = Query("", max_length=200),
                  current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Side-by-side factors for up to four candidates already in this need's match list."""
    if await too_many(f"search:candidates:{current['sub']}", limit=30, window_seconds=60):
        raise ApiError(429, "rate_limited")
    need = await _own(db, need_id, current)
    wanted = []
    for raw in ids.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            wanted.append(str(uuid.UUID(raw)))
        except ValueError:
            continue
    p = NeedParams(**(await _params(db, need)).params)
    result = await search_candidates(
        db, skills=p.skills, q=p.q, limit=50, has_fsp=p.has_fsp, work_goal=p.work_goal,
        need=p.spec(), employer_id=need.employer_id)
    picked = wanted[:4]
    items = anonymous_compare(result["items"], picked)
    if picked and len(items) != len(picked):
        raise ApiError(404, "not_found", "Кто-то из выбранных кандидатов недоступен")
    return {"items": items}


_NOTE_RATE = 30  # model calls per employer per hour
_NOTE_TTL = 86_400


@router.get("/{need_id}/candidates/{candidate_id}/ai-note")
async def ai_note(need_id: uuid.UUID, candidate_id: uuid.UUID,
                  current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Advisory model note on one card from this need's list. The score and the order stay as they are."""
    need = await _own(db, need_id, current)
    if await providers.refresh(db) is None:
        raise ApiError(503, "unavailable", "ИИ-помощник не подключён")
    p = NeedParams(**(await _params(db, need)).params)
    page = await _hydrate(db, await _matches_cached(db, need, p, 50, 0))
    card = next((c for c in page["items"] if c.get("candidate_id") == str(candidate_id)), None)
    if card is None:
        raise ApiError(404, "not_found", "Кандидата нет в подборке по этой потребности")
    need_facts = p.model_dump(include={"role", "grade", "skills", "nice_to_have"})
    known = second_opinion.facts(card, need_facts)
    digest = hashlib.sha256(json.dumps(known, ensure_ascii=False).encode()).hexdigest()[:32]
    key = f"ai:note:{need.id}:{digest}"
    redis = await _redis()
    if redis is not None:
        try:
            if cached := await redis.get(key):
                return {**json.loads(cached), "cached": True}
        except Exception:
            redis = None
    if await too_many(f"ai:note:{current['sub']}", limit=_NOTE_RATE, window_seconds=3600, fail_closed=True):
        raise ApiError(429, "rate_limited", headers={"Retry-After": "3600"})
    try:
        note = await second_opinion.second_opinion(card, need_facts)
    except Exception as e:
        logger.warning("AI note failed for need %s: %s", need.id, type(e).__name__)
        raise ApiError(503, "unavailable", "ИИ-помощник не ответил, попробуйте позже") from None
    logger.info("AI note for candidate %s, need %s, employer %s via %s, dropped %s",
                candidate_id, need.id, current["sub"], note["provider"], note["dropped"])
    if redis is not None:
        try:
            await redis.set(key, json.dumps(note, ensure_ascii=False), ex=_NOTE_TTL)
        except Exception:
            pass
    return {**note, "cached": False}


class ShortlistIn(BaseModel):
    status: Literal["shortlisted", "invited", "rejected"] = "shortlisted"
    note: str | None = Field(None, max_length=500)


@router.put("/{need_id}/shortlist/{candidate_id}")
async def shortlist(need_id: uuid.UUID, candidate_id: uuid.UUID, body: ShortlistIn,
                    current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    need = await _own(db, need_id, current)
    p = await db.get(Participant, candidate_id)
    if p is None or not p.discoverable:
        raise ApiError(404, "not_found", "Кандидат не найден")
    row = await db.scalar(select(NeedShortlist).where(NeedShortlist.need_id == need.id,
                                                      NeedShortlist.participant_id == candidate_id))
    params = NeedParams(**(await _params(db, need)).params)
    m = (await score_pool(db, [candidate_id], params.spec(), {}))[candidate_id]
    if row is None:
        row = NeedShortlist(need_id=need.id, participant_id=candidate_id, version=need.version)
        db.add(row)
    row.status, row.note, row.score = body.status, body.note, m.score
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ApiError(409, "conflict") from e
    return {"candidate_id": str(candidate_id), "status": row.status, "version": row.version, "score": row.score}


@router.delete("/{need_id}/shortlist/{candidate_id}")
async def unshortlist(need_id: uuid.UUID, candidate_id: uuid.UUID, current: dict = Depends(get_current_employer),
                      db: AsyncSession = Depends(get_db)):
    need = await _own(db, need_id, current)
    row = await db.scalar(select(NeedShortlist).where(NeedShortlist.need_id == need.id,
                                                      NeedShortlist.participant_id == candidate_id))
    if row is not None:
        await db.delete(row)
        await db.commit()
    return {"removed": row is not None}


def shortlist_page(items: list[dict], status: str | None) -> list[dict]:
    """Funnel counts stay on the full list. The page can show one status."""
    if status is None:
        return items
    return [item for item in items if item.get("status") == status]


@router.get("/{need_id}/shortlist")
async def get_shortlist(need_id: uuid.UUID, status: Literal["shortlisted", "invited", "rejected"] | None = None,
                        current: dict = Depends(get_current_employer),
                        db: AsyncSession = Depends(get_db)):
    need = await _own(db, need_id, current)
    rows = list(await db.scalars(select(NeedShortlist).where(NeedShortlist.need_id == need.id)
                                 .order_by(NeedShortlist.added_at)))
    # A withdrawn publication drops the card from the shortlist at once. The row stays, so the
    # decision returns if the candidate publishes again.
    people = {p.id: p for p in await db.scalars(select(Participant).where(
        Participant.id.in_([r.participant_id for r in rows])))} if rows else {}
    rows = [r for r in rows if (person := people.get(r.participant_id)) is not None and person.discoverable]
    cats = {c.participant_id: c for c in await db.scalars(select(CategoryAssignment).where(
        CategoryAssignment.participant_id.in_([r.participant_id for r in rows])))} if rows else {}
    need_role = ((await _params(db, need)).params or {}).get("role")
    confs = {}
    if need_role and rows:
        confs = {c.participant_id: c for c in await db.scalars(select(GradeConfirmation).where(
            GradeConfirmation.participant_id.in_([r.participant_id for r in rows]),
            GradeConfirmation.specialization == need_role))}
    funnel = {s: sum(1 for r in rows if r.status == s) for s in ("shortlisted", "invited", "rejected")}
    items = []
    for r in rows:
        cat = cats.get(r.participant_id)
        conf = confs.get(r.participant_id)
        role, grade, source, also = shown_category(
            cat.primary_role if cat else None, cat.grade if cat else None,
            cat.grade_source if cat else None,
            conf.specialization if conf else None, conf.grade if conf else None,
            "assessed" if conf else None)
        items.append({
            "candidate_id": str(r.participant_id), "status": r.status, "note": r.note, "score": r.score,
            "picked_on_version": r.version, "added_at": r.added_at.isoformat(),
            "role": role, "grade": grade, "grade_source": source, "also_primary": also,
        })
    return {"funnel": funnel, "items": shortlist_page(items, status)}
