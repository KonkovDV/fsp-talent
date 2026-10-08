import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import Consent, ConsentLog, Participant, Skill, VerifiableCredential
from app.models.profile import CategoryAssignment, DisciplineScore
from app.services.categorization import DISCIPLINE_LABELS
from app.services.guardian import token_participant, token_valid
from app.services.pdf_profile import profile_lines, render_profile_pdf
from app.services.profile import adult_cutoff
from app.services.search.cache import bump_bank_epoch
from app.services.skills import skill_line
from app.services.survey import SPECIALIZATIONS
from app.services.vc.issuer import issuer_document, verify_credential

router = APIRouter(prefix="/public", tags=["public"])

# A real W3C Data Integrity credential is a few hundred bytes.
# Reject oversized bodies before any JSON parsing or cryptographic work.
_MAX_VERIFY_BYTES = 65_536  # 64 KB


def _public_filter():
    """Named page / leaderboard / public credentials filter.

    Uses birth_date for the adulthood check — the stored is_minor flag is only
    a fallback for participants whose birth_date is unknown.
    """
    cutoff = adult_cutoff()
    adult = or_(
        and_(Participant.birth_date.is_not(None), Participant.birth_date <= cutoff),
        and_(Participant.birth_date.is_(None), Participant.is_minor.is_(False)),
    )
    # 152-FZ art. 10.1: data open to everyone needs an active consent to distribution, not just the toggle.
    consented = Participant.id.in_(select(Consent.subject_id).where(
        Consent.subject_type == "participant", Consent.kind == "pd_distribution", Consent.withdrawn_at.is_(None)))
    return (Participant.public_profile.is_(True), adult, consented)


def _public_skill(s: Skill) -> dict:
    """Source and date, without the resume quote: a quote can contain a phone or an address."""
    return {
        "name": s.name,
        "trust_level": s.trust_level,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "confirmed_at": s.confirmed_at.isoformat() if s.confirmed_at else None,
    }


@router.get("/demo")
async def demo_stand():
    """Whether this stand shows the jury trial and the jury accounts. No other settings."""
    return {"demo_mode": bool(settings.DEMO_MODE)}


@router.get("/issuer")
async def issuer():
    return issuer_document()


@router.get("/candidates/{participant_id}")
async def get_public_profile(participant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    p = await db.scalar(
        select(Participant)
        .where(Participant.id == participant_id, *_public_filter())
        .options(
            selectinload(Participant.skills),
            selectinload(Participant.discipline_scores),
            selectinload(Participant.category),
        )
    )
    if not p:
        raise HTTPException(404, "Публичный профиль не найден")
    cat = p.category
    return {
        "id": str(p.id),
        "display_name": p.display_name,
        "region": p.region,
        "primary_role": cat.primary_role if cat else None,
        "grade": cat.grade if cat else None,
        "grade_source": cat.grade_source if cat else None,
        "stack": cat.stack if cat else [],
        "explanation": cat.explanation if cat else [],
        "skills": [_public_skill(s) for s in p.skills if s.confirmed],
        "profile_pdf": f"/api/v1/public/candidates/{p.id}/profile.pdf",
        "discipline_scores": [
            {
                "discipline": ds.discipline,
                "label": DISCIPLINE_LABELS.get(ds.discipline, ds.discipline),
                "score": ds.score,
                "lcb": ds.lcb,
                "confidence": ds.confidence,
                "best_rank": ds.best_rank,
                "rank_assigned_at": ds.rank_assigned_at.isoformat() if ds.rank_assigned_at else None,
                "rank_order_ref": ds.rank_order_ref,
                "events_count": ds.events_count,
            }
            for ds in sorted(p.discipline_scores, key=lambda d: -d.lcb)
        ],
    }


@router.get("/candidates/{participant_id}/profile.pdf")
async def public_profile_pdf(participant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    p = await db.scalar(
        select(Participant)
        .where(Participant.id == participant_id, *_public_filter())
        .options(selectinload(Participant.skills), selectinload(Participant.discipline_scores),
                 selectinload(Participant.category))
    )
    if not p:
        raise HTTPException(404, "Публичный профиль не найден")
    cat = p.category
    lines = profile_lines(
        p.display_name,
        SPECIALIZATIONS.get(cat.primary_role, cat.primary_role) if cat else None,
        cat.grade if cat else None,
        [skill_line(s.name, s.trust_level) for s in p.skills if s.confirmed],
        [{"label": DISCIPLINE_LABELS.get(s.discipline, s.discipline), "lcb": s.lcb, "rank": s.best_rank,
          "rank_assigned_at": s.rank_assigned_at.isoformat() if s.rank_assigned_at else None,
          "rank_order_ref": s.rank_order_ref}
         for s in p.discipline_scores],
    )
    return Response(content=render_profile_pdf(lines), media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=profile.pdf",
                             "Cache-Control": "private, no-store"})


@router.get("/credentials/verify/{credential_id}")
async def verify_stored(credential_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    vc = await db.get(VerifiableCredential, credential_id)
    if not vc:
        raise HTTPException(404, "Удостоверение не найдено")
    visible = await db.scalar(
        select(Participant.id).where(Participant.id == vc.participant_id, *_public_filter())
    )
    if not visible:
        raise HTTPException(404, "Удостоверение не найдено")
    signed = verify_credential(vc.credential_json)
    revoked = vc.revoked_at is not None
    return {"valid": signed and not revoked, "signature": signed, "revoked": revoked,
            "credential": vc.credential_json}


def credential_uuid(document: dict) -> uuid.UUID | None:
    """The credential id, if the document names one. A foreign document stays signature-only."""
    raw = document.get("id")
    if not isinstance(raw, str):
        return None
    token = raw.removeprefix("urn:uuid:")
    try:
        return uuid.UUID(token)
    except ValueError:
        return None


@router.post("/credentials/verify")
async def verify_posted(request: Request, db: AsyncSession = Depends(get_db)):
    """Verify a W3C Verifiable Credential submitted as JSON.

    Body is capped at 64 KB before any JSON parsing or cryptographic work.
    This endpoint is public/unauthenticated, so the size guard is the primary
    defence against DoS via oversized payloads.
    """
    body = await request.body()
    if len(body) > _MAX_VERIFY_BYTES:
        raise HTTPException(413, "Payload too large (max 64 KB)")
    try:
        data = json.loads(body)
    except ValueError:
        raise HTTPException(422, "Invalid JSON")
    if not isinstance(data, dict):
        raise HTTPException(422, "Expected a JSON object")
    signed = verify_credential(data)
    revoked = False
    credential_id = credential_uuid(data)
    if signed and credential_id is not None:
        stored = await db.get(VerifiableCredential, credential_id)
        revoked = stored is not None and stored.revoked_at is not None
    return {"valid": signed and not revoked, "signature": signed, "revoked": revoked}


@router.get("/credentials/{participant_id}")
async def get_credentials(participant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    visible = await db.scalar(
        select(Participant.id).where(Participant.id == participant_id, *_public_filter())
    )
    if not visible:
        raise HTTPException(404, "Публичный профиль не найден")
    rows = await db.scalars(
        select(VerifiableCredential).where(VerifiableCredential.participant_id == participant_id)
    )
    out = []
    for vc in rows:
        signed = verify_credential(vc.credential_json)
        revoked = vc.revoked_at is not None
        out.append({
            "id": str(vc.id),
            "credential": vc.credential_json,
            "signature": signed,
            "revoked": revoked,
            "valid": signed and not revoked,
            "issued_at": vc.issued_at.isoformat() if vc.issued_at else None,
        })
    return out


@router.get("/credentials/{credential_id}/status")
async def credential_status(credential_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Revocation only. The body has no name, no result and no achievement."""
    vc = await db.get(VerifiableCredential, credential_id)
    if vc is None:
        raise HTTPException(404, "Удостоверение не найдено")
    return {
        "id": f"{settings.PUBLIC_BASE_URL}/api/v1/public/credentials/{vc.id}/status",
        "type": "FSPCredentialStatus",
        "revoked": vc.revoked_at is not None,
    }


@router.get("/leaderboard")
async def get_leaderboard(
    discipline: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(DisciplineScore, CategoryAssignment, Participant)
        .join(Participant, Participant.id == DisciplineScore.participant_id)
        .join(
            CategoryAssignment,
            CategoryAssignment.participant_id == DisciplineScore.participant_id,
            isouter=True,
        )
        .where(*_public_filter())
    )
    if discipline:
        q = q.where(DisciplineScore.discipline == discipline)
    else:
        best = (
            select(DisciplineScore.id)
            .distinct(DisciplineScore.participant_id)
            .order_by(DisciplineScore.participant_id, DisciplineScore.lcb.desc())
        )
        q = q.where(DisciplineScore.id.in_(best))
    rows = (await db.execute(q.order_by(DisciplineScore.lcb.desc()).limit(limit))).all()
    return [
        {
            "rank": i + 1,
            "participant_id": str(ds.participant_id),
            "display_name": p.display_name,
            "region": p.region,
            "discipline": ds.discipline,
            "label": DISCIPLINE_LABELS.get(ds.discipline, ds.discipline),
            "score": ds.score,
            "lcb": ds.lcb,
            "best_rank": ds.best_rank,
            "grade": cat.grade if cat else None,
        }
        for i, (ds, cat, p) in enumerate(rows)
    ]


@router.get("/assessment/items")
async def item_health(db: AsyncSession = Depends(get_db)):
    """Open statistics of the item bank: answers, solve rate against the model and leak status.

    z is (right − expected) / sd, with ability measured without the item's own family. z ≥ 3.5 on 30+
    answers sends the key to quarantine: it is no longer served and its answers stop counting.
    """
    from app.models.assessment import ItemStat
    rows = list(await db.scalars(select(ItemStat).order_by(ItemStat.z.desc())))
    return [{
        "item_key": r.item_key, "family_id": r.family_id, "level": r.level, "answers": r.n,
        "solve_rate": round(r.correct / r.n, 3) if r.n else None,
        "expected_rate": round(r.expected / r.n, 3) if r.n else None,
        "z": round(r.z, 2), "status": r.status, "b_offset": round(r.b_offset, 2), "sessions": r.sessions,
    } for r in rows]


_PSYCHOMETRICS_TTL = 300
_PSYCHOMETRICS_KEY = "method:psychometrics:v2:"


def _without_keys(payload: dict) -> dict:
    """The method page publishes parameters and counts. A stem or an answer key must not ride along."""
    forbidden = {"item_key", "stem", "answer", "right_answer", "answer_text"}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            found = forbidden & node.keys()
            if found:
                raise RuntimeError(f"сводка методики содержит {sorted(found)}")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return payload


@router.get("/assessment/psychometrics")
async def psychometrics(response: Response, spec: str = "backend", db: AsyncSession = Depends(get_db)):
    """Information at the grade cuts and exposure by family. No stems and no answer keys.

    The body is cached for five minutes: the curve does not depend on live answers, and the
    exposure counts move slowly. Cache-Control lets a browser keep the same copy.
    """
    from app.core.redis_client import get_redis
    from app.items.registry import BLUEPRINTS
    from app.models.assessment import ItemStat
    from app.services.psychometrics import bank_curve, summarize_exposure

    if spec not in BLUEPRINTS:
        raise HTTPException(400, "Неизвестная специализация")
    response.headers["Cache-Control"] = "public, max-age=300"
    key = _PSYCHOMETRICS_KEY + spec
    redis = None
    try:
        redis = await get_redis()
        cached = await redis.get(key)
    except Exception:
        cached = None
    if cached:
        return json.loads(cached)
    rows = list(await db.execute(
        select(ItemStat.family_id, ItemStat.level, ItemStat.n, ItemStat.cusum, ItemStat.status)))
    payload = _without_keys({**bank_curve(spec), **summarize_exposure(
        [(f, lvl, n, c, s) for f, lvl, n, c, s in rows])})
    if redis is not None:
        try:
            await redis.set(key, json.dumps(payload, ensure_ascii=False), ex=_PSYCHOMETRICS_TTL)
        except Exception:
            pass
    return payload


class GuardianConsentIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/guardian-consent")
async def guardian_consent(body: GuardianConsentIn, db: AsyncSession = Depends(get_db)):
    """The legal representative confirms by the signed link from the letter. Only then the card enters search."""
    pid = token_participant(body.token)
    p = await db.get(Participant, pid) if pid else None
    if p is None or p.deleted_at is not None or not token_valid(body.token, p.id, p.guardian_email):
        raise HTTPException(404, "Ссылка недействительна или устарела")
    if not p.minor_consent_given:
        p.minor_consent_given = True
        p.guardian_consent_at = datetime.now(UTC)
        db.add(ConsentLog(participant_id=p.id, event_type="guardian_consent", actor_id=p.id,
                          meta={"by": "guardian", "guardian_email": p.guardian_email}))
        await db.commit()
        await bump_bank_epoch()
    return {"ok": True, "display_name": p.display_name}
