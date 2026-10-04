from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_employer, get_current_participant
from app.services.ai.assistant import parse_query, parse_resume

router = APIRouter(prefix="/ai", tags=["ai"])


class ResumeIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


@router.post("/parse-resume")
async def parse_resume_endpoint(body: ResumeIn, current: dict = Depends(get_current_participant)):
    del current
    return await parse_resume(body.text)


class QueryIn(BaseModel):
    q: str = Field(min_length=1, max_length=300)


@router.post("/parse-query")
async def parse_query_endpoint(body: QueryIn, current: dict = Depends(get_current_employer)):
    del current
    return parse_query(body.q)
