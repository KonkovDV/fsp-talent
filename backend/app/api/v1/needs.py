"""Employer needs: versioned search profiles, matches with explanations, recommended categories, shortlist."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.models import CategoryAssignment, Need, NeedShortlist, NeedVersion, Participant
from app.services.matching import NeedSpec, anonymous_compare
from app.services.search.pipeline import score_pool, search_candidates
from app.services.skills import normalize_skill
from app.services.survey import INDUSTRIES, SPECIALIZATIONS
from app.services.vacancy_exam import form_exam

router = APIRouter(prefix="/needs", tags=["needs"])
Grade = Literal["junior", "middle", "senior", "lead"]


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
    q: str | None = Field(None, max_length=300)

    @model_validator(mode="after")
    def _check(self):
        if self.role and self.role not in SPECIALIZATIONS:
            raise ValueError("Неизвестная специализация")
        if self.industry and self.industry not in INDUSTRIES:
            raise ValueError("Неизвестная отрасль")
        if self.salary_from and self.salary_to and self.salary_from > self.salary_to:
            raise ValueError("Зарплата «от» больше, чем «до»")
        self.skills = sorted({n for s in self.skills if (n := normalize_skill(s))})
        self.nice_to_have = sorted({n for s in self.nice_to_have if (n := normalize_skill(s))} - set(self.skills))
        return self

    def spec(self) -> NeedSpec:
        return NeedSpec(role=self.role, grade=self.grade, skills=tuple(self.skills), nice=tuple(self.nice_to_have),
                        industry=self.industry, text=bool(self.q))


class NeedIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    params: NeedParams


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
    need.version += 1
    need.title = body.title
    need.updated_at = datetime.now(UTC)
    ver = NeedVersion(need_id=need.id, version=need.version, params=body.params.model_dump())
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


@router.get("/{need_id}/matches")
async def matches(need_id: uuid.UUID, limit: int = Query(20, ge=1, le=50),
                  current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Candidates for the need, ordered by the explainable score; role and grade are soft (neighbours count)."""
    if await too_many(f"search:candidates:{current['sub']}", limit=30, window_seconds=60):
        raise ApiError(429, "rate_limited")
    need = await _own(db, need_id, current)
    p = NeedParams(**(await _params(db, need)).params)
    result = await search_candidates(
        db, skills=p.skills, q=p.q, limit=limit, has_fsp=p.has_fsp, work_goal=p.work_goal, need=p.spec())
    listed = {str(pid) for pid in await db.scalars(
        select(NeedShortlist.participant_id).where(NeedShortlist.need_id == need.id))}
    for card in result["items"]:
        card["shortlisted"] = card["candidate_id"] in listed
    return {**result, "need": _out(need, await _params(db, need))}


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
    """Side-by-side factors for up to three candidates already in this need's match list."""
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
        db, skills=p.skills, q=p.q, limit=50, has_fsp=p.has_fsp, work_goal=p.work_goal, need=p.spec())
    return {"items": anonymous_compare(result["items"], wanted[:3])}


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


@router.get("/{need_id}/shortlist")
async def get_shortlist(need_id: uuid.UUID, current: dict = Depends(get_current_employer),
                        db: AsyncSession = Depends(get_db)):
    need = await _own(db, need_id, current)
    rows = list(await db.scalars(select(NeedShortlist).where(NeedShortlist.need_id == need.id)
                                 .order_by(NeedShortlist.added_at)))
    cats = {c.participant_id: c for c in await db.scalars(select(CategoryAssignment).where(
        CategoryAssignment.participant_id.in_([r.participant_id for r in rows])))} if rows else {}
    funnel = {s: sum(1 for r in rows if r.status == s) for s in ("shortlisted", "invited", "rejected")}
    return {"funnel": funnel, "items": [{
        "candidate_id": str(r.participant_id), "status": r.status, "note": r.note, "score": r.score,
        "picked_on_version": r.version, "added_at": r.added_at.isoformat(),
        "role": cats[r.participant_id].primary_role if r.participant_id in cats else None,
        "grade": cats[r.participant_id].grade if r.participant_id in cats else None,
    } for r in rows]}
