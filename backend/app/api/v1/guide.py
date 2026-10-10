"""A short pointer to a page this user can open. The question is not stored and not sent on."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_any_auth
from app.api.errors import ApiError
from app.core.ratelimit import too_many
from app.services.guide import guide

router = APIRouter(prefix="/guide", tags=["guide"])


class GuideIn(BaseModel):
    question: str = Field(min_length=2, max_length=200)


@router.post("/ask")
async def ask_guide(body: GuideIn, current: dict = Depends(get_any_auth)):
    if await too_many(f"guide:{current['sub']}", limit=30, window_seconds=3600):
        raise ApiError(429, "rate_limited", "Слишком много вопросов. Подождите час.")
    role = current.get("role")
    if role not in ("participant", "employer"):
        raise ApiError(403, "forbidden", "Подсказка доступна кандидату и компании")
    return guide(body.question, role)
