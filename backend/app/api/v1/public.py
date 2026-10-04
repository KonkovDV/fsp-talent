import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models import Participant, VerifiableCredential
from app.models.profile import CategoryAssignment, DisciplineScore
from app.services.categorization import DISCIPLINE_LABELS
from app.services.profile import adult_cutoff
from app.services.vc.issuer import issuer_document, verify_credential

router = APIRouter(prefix="/public", tags=["public"])


def _public_filter():
    """Named page, leaderboard and public credentials. A minor stays off even if the flag is stale."""
    cutoff = adult_cutoff()
    adult = or_(
        and_(Participant.birth_date.is_not(None), Participant.birth_date <= cutoff),
        and_(Participant.birth_date.is_(None), Participant.is_minor.is_(False)),
    )
    return (Participant.public_profile.is_(True), adult)


@router.get("/issuer")
async def issuer():
    return issuer_document()


@router.get("/candidates/{participant_id}")
async def get_public_profile(participant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    p = await db.scalar(
        select(Participant).where(Participant.id == participant_id, *_public_filter()).options(
            selectinload(Participant.skills), selectinload(Participant.discipline_scores),
            selectinload(Participant.category)))
    if not p:
        raise HTTPException(404, "Публичный профиль не найден")
    cat = p.category
    return {
        "id": str(p.id), "display_name": p.display_name, "region": p.region,
        "primary_role": cat.primary_role if cat else None,
        "grade": cat.grade if cat else None,
        "grade_source": cat.grade_source if cat else None,
        "stack": cat.stack if cat else [],
        "explanation": cat.explanation if cat else [],
        "skills": [s.name for s in p.skills if s.confirmed],
        "discipline_scores": [
            {"discipline": ds.discipline, "label": DISCIPLINE_LABELS.get(ds.discipline, ds.discipline),
             "score": ds.score, "lcb": ds.lcb, "confidence": ds.confidence,
             "best_rank": ds.best_rank, "events_count": ds.events_count}
            for ds in sorted(p.discipline_scores, key=lambda d: -d.lcb)
        ],
    }


@router.get("/credentials/verify/{credential_id}")
async def verify_stored(credential_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    vc = await db.get(VerifiableCredential, credential_id)
    if not vc:
        raise HTTPException(404, "Удостоверение не найдено")
    visible = await db.scalar(select(Participant.id).where(Participant.id == vc.participant_id, *_public_filter()))
    if not visible:
        raise HTTPException(404, "Удостоверение не найдено")
    return {"valid": verify_credential(vc.credential_json), "credential": vc.credential_json}


@router.post("/credentials/verify")
async def verify_posted(body: dict):
    return {"valid": verify_credential(body)}


@router.get("/credentials/{participant_id}")
async def get_credentials(participant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    visible = await db.scalar(select(Participant.id).where(Participant.id == participant_id, *_public_filter()))
    if not visible:
        raise HTTPException(404, "Публичный профиль не найден")
    rows = await db.scalars(select(VerifiableCredential).where(VerifiableCredential.participant_id == participant_id))
    return [{"id": str(vc.id), "credential": vc.credential_json,
             "valid": verify_credential(vc.credential_json),
             "issued_at": vc.issued_at.isoformat() if vc.issued_at else None} for vc in rows]


@router.get("/leaderboard")
async def get_leaderboard(discipline: str | None = None, limit: int = Query(20, ge=1, le=50),
                          db: AsyncSession = Depends(get_db)):
    q = (select(DisciplineScore, CategoryAssignment, Participant)
         .join(Participant, Participant.id == DisciplineScore.participant_id)
         .join(CategoryAssignment, CategoryAssignment.participant_id == DisciplineScore.participant_id, isouter=True)
         .where(*_public_filter()))
    if discipline:
        q = q.where(DisciplineScore.discipline == discipline)
    else:
        best = (select(DisciplineScore.id)
                .distinct(DisciplineScore.participant_id)
                .order_by(DisciplineScore.participant_id, DisciplineScore.lcb.desc()))
        q = q.where(DisciplineScore.id.in_(best))
    rows = (await db.execute(q.order_by(DisciplineScore.lcb.desc()).limit(limit))).all()
    return [{
        "rank": i + 1, "participant_id": str(ds.participant_id), "display_name": p.display_name,
        "region": p.region, "discipline": ds.discipline,
        "label": DISCIPLINE_LABELS.get(ds.discipline, ds.discipline),
        "score": ds.score, "lcb": ds.lcb, "best_rank": ds.best_rank,
        "grade": cat.grade if cat else None,
    } for i, (ds, cat, p) in enumerate(rows)]
