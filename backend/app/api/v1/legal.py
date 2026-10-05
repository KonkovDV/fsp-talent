"""Legal documents and the person's own consents (152-FZ art. 9 and 10.1)."""
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_any_auth
from app.api.errors import ApiError
from app.core.database import get_db
from app.legal import documents, get_document
from app.models import Consent, Participant
from app.services.identity import give_consent, withdraw_consent

router = APIRouter(tags=["legal"])


def _summary(doc) -> dict:
    return {"kind": doc.kind, "version": doc.version, "title": doc.title, "roles": list(doc.roles),
            "required": doc.required, "sha256": doc.sha256}


@router.get("/legal/documents")
async def list_documents(role: str | None = None):
    return [_summary(d) for d in documents().values() if role is None or role in d.roles]


@router.get("/legal/documents/{kind}")
async def read_document(kind: str):
    doc = get_document(kind)
    if doc is None:
        raise ApiError(404, "consent_unknown")
    return {**_summary(doc), "body_md": doc.body_md}


def _subject(current: dict) -> tuple[str, uuid.UUID]:
    role = current.get("role")
    if role not in ("participant", "employer"):
        raise ApiError(403, "forbidden")
    return role, uuid.UUID(current["sub"])


@router.get("/me/consents")
async def my_consents(current: dict = Depends(get_any_auth), db: AsyncSession = Depends(get_db)):
    role, subject_id = _subject(current)
    rows = list(await db.scalars(select(Consent).where(
        Consent.subject_type == role, Consent.subject_id == subject_id).order_by(Consent.given_at.desc())))
    out = []
    for doc in documents().values():
        if role not in doc.roles:
            continue
        active = next((r for r in rows if r.kind == doc.kind and r.withdrawn_at is None), None)
        out.append({
            **_summary(doc),
            "active": active is not None,
            "given_at": active.given_at.isoformat() if active else None,
            "accepted_version": active.version if active else None,
            "outdated": bool(active and active.sha256 != doc.sha256),
            "history": [{"version": r.version, "given_at": r.given_at.isoformat(),
                         "withdrawn_at": r.withdrawn_at.isoformat() if r.withdrawn_at else None}
                        for r in rows if r.kind == doc.kind],
        })
    return out


class ConsentIn(BaseModel):
    kind: str


@router.post("/me/consents", status_code=201)
async def give(body: ConsentIn, request: Request, current: dict = Depends(get_any_auth),
               db: AsyncSession = Depends(get_db)):
    role, subject_id = _subject(current)
    if role == "participant" and body.kind == "pd_distribution":
        p = await db.get(Participant, subject_id)
        if p is not None and p.minor_now():
            raise ApiError(403, "forbidden", "Публичная страница недоступна несовершеннолетним")
    consent = await give_consent(db, role, subject_id, body.kind, request)
    await db.commit()
    return {"kind": consent.kind, "version": consent.version, "given_at": consent.given_at.isoformat()}


@router.delete("/me/consents/{kind}")
async def withdraw(kind: str, request: Request, current: dict = Depends(get_any_auth),
                   db: AsyncSession = Depends(get_db)):
    role, subject_id = _subject(current)
    if get_document(kind) is None:
        raise ApiError(404, "consent_unknown")
    consent = await withdraw_consent(db, role, subject_id, kind, request)
    effects: list[str] = []
    if role == "participant":
        p = await db.get(Participant, subject_id)
        if p is not None and kind in ("pd_distribution", "pd_candidate") and p.public_profile:
            p.public_profile = False
            effects.append("Публичная страница выключена")
        if p is not None and kind == "pd_candidate":
            p.is_visible = False
            effects.append("Карточка скрыта из поиска; данные будут удалены в течение 30 дней "
                           "(ч. 5 ст. 21 152-ФЗ), если их хранение не требует закон")
    await db.commit()
    return {"kind": kind, "withdrawn": consent is not None, "effects": effects}
