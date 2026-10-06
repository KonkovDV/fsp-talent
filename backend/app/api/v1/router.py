from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1 import (
    ai,
    assessment,
    auth,
    candidates,
    employer,
    fsp_id_demo,
    legal,
    needs,
    notifications,
    offers,
    public,
    search,
    vacancies,
)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorOut(BaseModel):
    """Every error has this shape; the list of codes is in docs/API_ERRORS.md."""
    error: ErrorBody
    detail: Any


ERRORS = {code: {"model": ErrorOut, "description": text} for code, text in {
    401: "Нет или неверный токен (unauthorized, invalid_credentials)",
    403: "Нет прав или email не подтверждён (forbidden, email_not_verified)",
    404: "Не найдено (not_found, need_not_found, consent_unknown)",
    409: "Конфликт состояния (conflict, email_taken, session_closed, item_token_invalid, ...)",
    422: "Ошибка валидации (validation_error, consent_required, survey_required)",
    429: "Лимит запросов или попыток (rate_limited, retake_cooldown, grade_locked), есть Retry-After",
}.items()}

api_router = APIRouter(prefix="/api/v1", responses=ERRORS)
api_router.include_router(auth.router)
api_router.include_router(candidates.router)
api_router.include_router(search.router)
api_router.include_router(offers.router)
api_router.include_router(vacancies.router)
api_router.include_router(ai.router)
api_router.include_router(public.router)
api_router.include_router(assessment.router)
api_router.include_router(employer.router)
api_router.include_router(legal.router)
api_router.include_router(needs.router)
api_router.include_router(notifications.router)
api_router.include_router(fsp_id_demo.router)
