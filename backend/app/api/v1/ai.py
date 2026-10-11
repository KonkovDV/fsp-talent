import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer, get_current_participant
from app.core.database import get_db
from app.services.ai import providers
from app.services.ai.assistant import parse_query, parse_resume
from app.services.identity import consent_is_current
from app.services.skills import with_resume_token

router = APIRouter(prefix="/ai", tags=["ai"])


class ResumeIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


@router.post("/parse-resume")
async def parse_resume_endpoint(body: ResumeIn, current: dict = Depends(get_current_participant),
                                db: AsyncSession = Depends(get_db)):
    await providers.refresh()
    # 152-FZ art. 6 p. 3: the resume goes to a model processor only under the consent text that names it.
    allowed = await consent_is_current(db, "participant", uuid.UUID(str(current["sub"])), "pd_candidate")
    parsed = await parse_resume(body.text, allow_llm=allowed)
    if not allowed:
        parsed["consent_outdated"] = True
    return with_resume_token(str(current["sub"]), parsed)


class QueryIn(BaseModel):
    q: str = Field(min_length=1, max_length=300)


@router.post("/parse-query")
async def parse_query_endpoint(body: QueryIn, current: dict = Depends(get_current_employer)):
    del current
    return parse_query(body.q)
