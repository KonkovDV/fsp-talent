import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.services.cities import WORK_FORMATS, city_name
from app.services.demand import note_card_views
from app.services.matching import NeedSpec
from app.services.search.pipeline import bank_grid, search_candidates
from app.services.skills import extract_skills, normalize_skill

router = APIRouter(prefix="/search", tags=["search"])

_SEARCH_RATE = 30  # per employer per minute


def implied_role(text: str | None, chosen: str | None) -> str | None:
    """A Russian or English role word fills an empty specialization filter. An explicit filter wins."""
    if chosen:
        return chosen
    if not (text or "").strip():
        return None
    from app.services.ai.assistant import parse_query
    return parse_query(text or "").get("role")


def _wanted(skill_list: list[str], q: str | None) -> tuple[str, ...]:
    names = {n for s in skill_list if (n := normalize_skill(s))}
    if q:
        names |= {e.skill for e in extract_skills(q)}
    return tuple(sorted(names))


@router.get("/bank")
async def bank(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Showcase of the bank: specialization × grade, people and how many confirmed the grade by test.

    Cells with fewer than five people come back hidden. A click in the interface opens the search with filters.
    """
    return await bank_grid(db)


@router.get("/candidates")
async def search(
    q: str | None = Query(None, max_length=300),
    role: str | None = None,
    grade: str | None = None,
    discipline: str | None = None,
    min_rank: str | None = None,
    skills: str | None = Query(None, max_length=400, description="Через запятую"),
    limit: int = Query(20, ge=1, le=50),
    fresh_days: int | None = Query(None, ge=1, le=90, description="Только профили, созданные за последние N дней"),
    assessed_only: bool = Query(False, description="Только кандидаты с грейдом, подтверждённым тестом"),
    has_fsp: bool | None = Query(None, description="true — только с историей ФСП, false — только без неё"),
    work_goal: str | None = Query(None, pattern="^(job|internship)$", description="internship — режим стажировки"),
    city: str | None = Query(None, max_length=40,
                            description="Город из справочника. Входит в балл, из выдачи не убирает"),
    work_format: str | None = Query(None, pattern="^(office|hybrid|remote)$",
                                    description="Формат работы. Входит в балл, из выдачи не убирает"),
    industry: str | None = Query(None, max_length=40),
    grade_span: str = Query("near", pattern="^(exact|near|wide)$"),
    grade_match: str | None = Query(None, pattern="^(exact|plus_minus|any)$"),
    current: dict = Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
):
    employer_id = current["sub"]
    if await too_many(f"search:candidates:{employer_id}", limit=_SEARCH_RATE, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов. Подождите минуту.",
            headers={"Retry-After": "60"},
        )
    skill_list = [s.strip() for s in skills.split(",") if s.strip()] if skills else []
    role = implied_role(q, role)
    named = city_name(city) if city else None
    if city and named is None:
        raise ApiError(422, "validation_error", "Город выберите из справочника")
    if work_format and work_format not in WORK_FORMATS:
        raise ApiError(422, "validation_error", "Неизвестный формат работы")
    page = await search_candidates(
        db, role=role or None, grade=grade or None, discipline=discipline or None,
        min_rank=min_rank or None, skills=skill_list, q=q or None, limit=limit, fresh_days=fresh_days,
        assessed_only=assessed_only, has_fsp=has_fsp, work_goal=work_goal,
        city=named, work_format=work_format,
        grade_span={"exact": "exact", "plus_minus": "plus_minus", "any": "any"}.get(grade_match or "", grade_span),
        need=NeedSpec(role=role or None, grade=grade or None, skills=_wanted(skill_list, q),
                      industry=industry or None, text=bool(q)),
        employer_id=uuid.UUID(employer_id),
    )
    shown: list[uuid.UUID] = []
    for card in page.get("items") or []:
        raw = card.get("candidate_id") if isinstance(card, dict) else None
        try:
            shown.append(uuid.UUID(str(raw)))
        except (TypeError, ValueError):
            continue
    await note_card_views(db, uuid.UUID(employer_id), shown)
    return page
