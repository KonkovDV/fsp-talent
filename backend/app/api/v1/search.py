from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.services.search.pipeline import search_candidates

router = APIRouter(prefix="/search", tags=["search"])

_SEARCH_RATE = 30  # per employer per minute


@router.get("/candidates")
async def search(
    q: str | None = Query(None, max_length=300),
    role: str | None = None,
    grade: str | None = None,
    discipline: str | None = None,
    min_rank: str | None = None,
    skills: str | None = Query(None, max_length=400, description="Через запятую"),
    limit: int = Query(20, ge=1, le=50),
    assessed_only: bool = Query(False, description="Только кандидаты с грейдом, подтверждённым тестом"),
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
    return await search_candidates(
        db, role=role or None, grade=grade or None, discipline=discipline or None,
        min_rank=min_rank or None, skills=skill_list, q=q or None, limit=limit,
        assessed_only=assessed_only,
    )
