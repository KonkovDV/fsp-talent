"""Public catalog of RFC 9457 problem classes. No account and no personal data."""
from fastapi import APIRouter

from app.api.errors import ApiError
from app.api.problems import CLASSES, catalog

router = APIRouter(tags=["problems"])


@router.get("/problems")
async def list_problems():
    return catalog()


@router.get("/problems/{problem}")
async def read_problem(problem: str):
    key = problem.upper()
    if key not in CLASSES:
        raise ApiError(404, "not_found", "Нет такого класса ошибки")
    row = next(item for item in catalog() if item["problem"] == key)
    return row
