from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.core.database import get_db
from app.services.search.pipeline import search_candidates

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/candidates")
async def search(
    q: str | None = Query(None, max_length=300),
    role: str | None = None,
    grade: str | None = None,
    discipline: str | None = None,
    min_rank: str | None = None,
    skills: str | None = Query(None, max_length=400, description="Через запятую"),
    limit: int = Query(20, ge=1, le=50),
    current: dict = Depends(get_current_employer),
    db: AsyncSession = Depends(get_db),
):
    del current
    skill_list = [s.strip() for s in skills.split(",") if s.strip()] if skills else []
    return await search_candidates(db, role=role or None, grade=grade or None, discipline=discipline or None,
                                   min_rank=min_rank or None, skills=skill_list, q=q or None, limit=limit)
