"""A demo desk for vacancy complaints and model item drafts. It does not exist outside the demo stand.

The printed employer account opens it. Closing a vacancy does not ban a person
and does not hide the candidate bank. A reviewed draft never enters the test.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.core.config import settings
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.models import AiProvider, Complaint, Employer, ItemDraft, Vacancy
from app.models.ai_provider import open_secret, seal_secret
from app.services import totp
from app.services.ai import drafts, providers
from app.services.ai.assistant import has_identity

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/moderation", tags=["moderation"])
DRAFTS_PER_MINUTE = 5

MODERATORS = frozenset({"hr@sibcode.demo"})
LABELS = {
    "не_вакансия": "fake",
    "зарплата_не_та": "salary",
    "оскорбление": "discrimination",
    "сбор_данных": "spam",
    "другое": "other",
}


def may_moderate(demo: bool, email: str | None) -> bool:
    return bool(demo) and (email or "") in MODERATORS


async def _desk(current: dict, db: AsyncSession, *, factor: bool = True) -> Employer:
    employer = await db.get(Employer, uuid.UUID(current["sub"]))
    if employer is None or not may_moderate(settings.DEMO_MODE, employer.email):
        raise ApiError(404, "not_found", "Раздел не найден")
    if factor and employer.totp_secret and not totp.unlocked(employer.totp_verified_at, datetime.now(UTC)):
        raise ApiError(403, "totp_required")
    return employer


class TotpIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


def _factor_out(employer: Employer) -> dict:
    now = datetime.now(UTC)
    open_now = totp.unlocked(employer.totp_verified_at, now)
    return {"enrolled": bool(employer.totp_secret), "unlocked": open_now,
            "unlocked_until": (employer.totp_verified_at + totp.UNLOCK).isoformat() if open_now else None}


@router.get("/totp")
async def factor_state(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Whether the desk asks for a code. Turning the factor on or off is a server console command."""
    return _factor_out(await _desk(current, db, factor=False))


@router.post("/totp")
async def unlock_desk(body: TotpIn, current: dict = Depends(get_current_employer),
                      db: AsyncSession = Depends(get_db)):
    employer = await _desk(current, db, factor=False)
    if not employer.totp_secret:
        raise ApiError(409, "conflict", "Второй фактор не включён")
    if await too_many(f"moderation:totp:{employer.id}", limit=5, fail_closed=True):
        raise ApiError(429, "rate_limited")
    now = datetime.now(UTC)
    step = totp.accept(totp.open_secret(str(employer.id), employer.totp_secret), body.code, now,
                       employer.totp_last_step)
    if step is None:
        raise ApiError(422, "totp_invalid")
    employer.totp_last_step, employer.totp_verified_at = step, now
    await db.commit()
    return _factor_out(employer)


@router.get("/complaints")
async def complaints(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    await _desk(current, db)
    rows = list(await db.scalars(select(Complaint).order_by(Complaint.created_at.desc()).limit(100)))
    return [{
        "id": str(row.id),
        "reason": LABELS.get(row.reason, "other"),
        "vacancy_id": str(row.vacancy_id) if row.vacancy_id else None,
        "offer_id": str(row.offer_id) if row.offer_id else None,
        "created_at": row.created_at.isoformat(),
    } for row in rows]


class DraftIn(BaseModel):
    spec: str = Field(max_length=30)
    topic: str = Field(max_length=40)
    level: int = Field(ge=1, le=5)


class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(None, max_length=500)


def _draft_out(row: ItemDraft) -> dict:
    return {
        "id": str(row.id), "spec": row.spec, "topic": row.topic, "level": row.level, "stem": row.stem,
        "key": row.key, "status": row.status, "note": row.note, "created_at": row.created_at.isoformat(),
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


@router.get("/item-drafts")
async def item_drafts(status: Literal["pending", "approved", "rejected"] = "pending",
                      current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Drafts two models agreed on. Approval marks a starting point for a family author; the test never serves it."""
    await _desk(current, db)
    await providers.refresh()
    rows = list(await db.scalars(
        select(ItemDraft).where(ItemDraft.status == status).order_by(ItemDraft.created_at.desc()).limit(100)))
    return {"model_ready": drafts.ready() is None, "items": [_draft_out(row) for row in rows]}


@router.post("/item-drafts", status_code=201)
async def request_draft(body: DraftIn, current: dict = Depends(get_current_employer),
                        db: AsyncSession = Depends(get_db)):
    await _desk(current, db)
    wrong = drafts.brief_error(body.spec, body.topic, body.level)
    if wrong:
        raise ApiError(422, "validation_error", wrong)
    await providers.refresh()
    if drafts.ready() is not None:
        raise ApiError(503, "unavailable", "Модели для черновиков не подключены: нужны две разные модели")
    if await too_many(f"moderation:drafts:{current['sub']}", limit=DRAFTS_PER_MINUTE):
        raise ApiError(429, "rate_limited")
    verdict, row = await drafts.queue_draft(db, body.spec, body.topic, body.level)
    await db.commit()
    return {"accepted": verdict.accepted, "reason": verdict.reason, "draft": _draft_out(row) if row else None}


@router.post("/item-drafts/{draft_id}/review")
async def review_draft(draft_id: uuid.UUID, body: ReviewIn, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    await _desk(current, db)
    row = await db.get(ItemDraft, draft_id, with_for_update=True)
    if row is None:
        raise ApiError(404, "not_found", "Черновик не найден")
    try:
        drafts.review(row, body.decision, (body.note or "").strip() or None, datetime.now(UTC))
    except ValueError as exc:
        if str(exc) == "identity":
            raise ApiError(422, "validation_error", "В заметке не должно быть имени, почты или телефона") from exc
        raise ApiError(409, "conflict", "Черновик уже разобран") from exc
    await db.commit()
    return _draft_out(row)


@router.post("/vacancies/{vacancy_id}/close")
async def close_vacancy(vacancy_id: uuid.UUID, current: dict = Depends(get_current_employer),
                        db: AsyncSession = Depends(get_db)):
    await _desk(current, db)
    vacancy = await db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise ApiError(404, "not_found", "Вакансия не найдена")
    if not vacancy.is_open:
        raise ApiError(409, "conflict", "Вакансия уже закрыта")
    vacancy.is_open = False
    await db.commit()
    return {"id": str(vacancy.id), "is_open": False}


class ProviderIn(BaseModel):
    kind: Literal["gigachat", "yandex", "cloudru", "mws"]
    label: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=100)
    check_model: str | None = Field(None, max_length=100)
    params: dict[str, str] = Field(default_factory=dict, max_length=4)
    secret: str = Field(min_length=1, max_length=2000)


def _provider_out(row: AiProvider) -> dict:
    """Never the key: only that one is stored."""
    return {"id": str(row.id), "kind": row.kind, "kind_label": providers.KINDS[row.kind].label, "label": row.label,
            "model": row.model, "check_model": row.check_model, "params": row.params or {},
            "is_active": row.is_active, "created_at": row.created_at.isoformat(),
            "activated_at": row.activated_at.isoformat() if row.activated_at else None}


async def _key_desk(current: dict, db: AsyncSession) -> Employer:
    employer = await _desk(current, db)
    if not employer.totp_secret:
        raise ApiError(403, "totp_required", "Ключи провайдеров меняются только под вторым фактором: "
                                             "включите его командой python -m app.services.totp enroll")
    return employer


async def _provider(db: AsyncSession, provider_id: uuid.UUID) -> AiProvider:
    row = await db.get(AiProvider, provider_id, with_for_update=True)
    if row is None:
        raise ApiError(404, "not_found", "Провайдер не найден")
    return row


@router.get("/ai-providers")
async def list_providers(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """The fixed provider list for the form, the saved ones and which model answers right now."""
    employer = await _desk(current, db)
    rows = list(await db.scalars(select(AiProvider).order_by(AiProvider.created_at.desc()).limit(50)))
    in_use = await providers.refresh(db, force=True)
    return {
        "kinds": [{"kind": k, "label": v.label, "params": list(v.params), "hint": v.hint, "hosts": list(v.hosts)}
                  for k, v in providers.KINDS.items()],
        "items": [_provider_out(row) for row in rows],
        "in_use": None if in_use is None else {"source": in_use.source, "kind": in_use.kind, "model": in_use.model},
        "can_edit": bool(employer.totp_secret),
    }


@router.post("/ai-providers", status_code=201)
async def add_provider(body: ProviderIn, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db)):
    employer = await _key_desk(current, db)
    secret = body.secret.strip()
    check_model = (body.check_model or "").strip() or None
    try:
        params = providers.validate(body.kind, body.model.strip(), check_model, body.params, secret)
    except ValueError as exc:
        raise ApiError(422, "validation_error", str(exc)) from exc
    if has_identity(body.label):
        raise ApiError(422, "validation_error", "В названии не должно быть имени, почты или телефона")
    row = AiProvider(id=uuid.uuid4(), kind=body.kind, label=body.label.strip(), model=body.model.strip(),
                     check_model=check_model, params=params, is_active=False, created_at=datetime.now(UTC))
    row.secret = seal_secret(row.id, secret)
    db.add(row)
    await db.commit()
    logger.info("AI provider %s (%s) added by employer %s", row.id, row.kind, employer.id)
    return _provider_out(row)


@router.post("/ai-providers/{provider_id}/activate")
async def activate_provider(provider_id: uuid.UUID, current: dict = Depends(get_current_employer),
                            db: AsyncSession = Depends(get_db)):
    employer = await _key_desk(current, db)
    row = await _provider(db, provider_id)
    await db.execute(update(AiProvider).where(AiProvider.is_active.is_(True), AiProvider.id != row.id)
                     .values(is_active=False))
    row.is_active, row.activated_at = True, datetime.now(UTC)
    await db.commit()
    providers.forget()
    logger.info("AI provider %s (%s) activated by employer %s", row.id, row.kind, employer.id)
    return _provider_out(row)


@router.post("/ai-providers/deactivate")
async def deactivate_providers(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Back to GigaChat from the server environment, or no model at all when it has no key."""
    employer = await _key_desk(current, db)
    await db.execute(update(AiProvider).where(AiProvider.is_active.is_(True)).values(is_active=False))
    await db.commit()
    providers.forget()
    logger.info("AI providers switched off by employer %s", employer.id)
    return {"ok": True}


@router.delete("/ai-providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: uuid.UUID, current: dict = Depends(get_current_employer),
                          db: AsyncSession = Depends(get_db)):
    employer = await _key_desk(current, db)
    row = await _provider(db, provider_id)
    await db.delete(row)
    await db.commit()
    providers.forget()
    logger.info("AI provider %s deleted by employer %s", provider_id, employer.id)


@router.post("/ai-providers/{provider_id}/check")
async def check_provider(provider_id: uuid.UUID, current: dict = Depends(get_current_employer),
                         db: AsyncSession = Depends(get_db)):
    """One short request without any personal data. The answer text is not returned, only whether it came."""
    await _key_desk(current, db)
    if await too_many(f"moderation:ai-check:{current['sub']}", limit=3):
        raise ApiError(429, "rate_limited")
    row = await _provider(db, provider_id)
    provider = providers.Provider(row.kind, row.model, row.check_model, open_secret(row), dict(row.params or {}),
                                  "db", str(row.id))
    try:
        reply = await providers.chat(provider, row.model, "Ответь одним словом.", "Скажи: готово", limit=100)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, providers.ProviderError) else type(exc).__name__
        return {"ok": False, "reason": reason[:200]}
    return {"ok": bool(reply.strip()), "reason": None}
