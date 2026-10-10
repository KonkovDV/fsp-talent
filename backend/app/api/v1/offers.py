import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer
from app.api.errors import ApiError
from app.api.v1.messages import unread_counts
from app.core.database import get_db
from app.core.idempotency import (
    IdempotencyConflict,
    IdempotencyUnavailable,
    fingerprint,
    idem_abort,
    idem_begin,
    idem_finish,
)
from app.core.ratelimit import RateLimitUnavailable, too_many
from app.models import AccessLog, CategoryAssignment, Employer, Offer, OfferFlag, Participant
from app.services.market import market_flag, quartiles, reason_shares, role_median, salary_gap_hint
from app.services.notify import Outbox, notify, salary
from app.services.offer_perks import PERKS, clean_perks
from app.services.offers import expire_if_stale, expire_stale, reinvite_after
from app.services.practice_track import next_stage
from app.services.privacy import contacts_allowed
from app.services.salary_net import as_gross
from app.services.trust_level import invite_limit, next_step, trust_level

router = APIRouter(prefix="/offers", tags=["offers"])


def _eid(current: dict) -> uuid.UUID:
    return uuid.UUID(current["sub"])


class OfferCreate(BaseModel):
    candidate_id: uuid.UUID
    salary_from_gross: int = Field(gt=0, le=100_000_000)
    salary_to_gross: int = Field(gt=0, le=100_000_000)
    currency: Literal["RUB"] = "RUB"
    role: str = Field(min_length=2, max_length=100)
    work_format: Literal["remote", "office", "hybrid"] = "remote"
    message: str | None = Field(None, max_length=2000)
    # TZ 2.2 п.2: how the candidate reaches the company (email, Telegram, phone of the recruiter).
    contact_method: str = Field(min_length=3, max_length=300)
    salary_basis: Literal["gross", "net"] = "gross"
    perks: list[str] = Field(default_factory=list, max_length=8)
    practice: bool = False

    @model_validator(mode="after")
    def _range(self):
        self.salary_from_gross = as_gross(self.salary_from_gross, self.salary_basis)
        self.salary_to_gross = as_gross(self.salary_to_gross, self.salary_basis)
        if self.salary_to_gross < self.salary_from_gross:
            raise ValueError("Верхняя граница зарплаты меньше нижней")
        self.perks = clean_perks(self.perks)
        return self


def _offer_out(o: Offer) -> dict:
    return {
        "id": str(o.id), "candidate_id": str(o.candidate_id), "role": o.role,
        "salary_from": o.salary_from_gross, "salary_to": o.salary_to_gross,
        "currency": o.currency, "work_format": o.work_format, "message": o.message,
        "status": o.status, "created_at": o.created_at.isoformat(),
        "expires_at": o.expires_at.isoformat() if o.expires_at else None,
        "contact_method": o.contact_method,
        "perks": [{"code": code, "label": PERKS[code]} for code in (o.perks or []) if code in PERKS],
        "practice_stage": o.practice_stage,
        "candidate_viewed_at": o.candidate_viewed_at.isoformat() if o.candidate_viewed_at else None,
        "contacts_available": o.status == "accepted" and o.contacts_revoked_at is None,
        "contacts_revoked_at": o.contacts_revoked_at.isoformat() if o.contacts_revoked_at else None,
        "contacts_revealed_at": o.contacts_revealed_at.isoformat() if o.contacts_revealed_at else None,
        "decline_reason": o.decline_reason,
    }


class SalaryPreview(BaseModel):
    candidate_id: uuid.UUID
    salary_to_gross: int = Field(gt=0, le=100_000_000)
    salary_from_gross: int | None = Field(None, gt=0, le=100_000_000)
    salary_basis: Literal["gross", "net"] = "gross"

    @model_validator(mode="after")
    def _as_gross(self):
        self.salary_to_gross = as_gross(self.salary_to_gross, self.salary_basis)
        if self.salary_from_gross:
            self.salary_from_gross = as_gross(self.salary_from_gross, self.salary_basis)
        return self


@router.post("/preview")
async def preview_offer(body: SalaryPreview, current: dict = Depends(get_current_employer),
                        db: AsyncSession = Depends(get_db)):
    """Hint only: the invitation can still be sent when the range is below the candidate's ask."""
    if await db.get(Employer, _eid(current)) is None:
        raise HTTPException(404, "Работодатель не найден")
    candidate = await db.get(Participant, body.candidate_id)
    if not candidate or not candidate.discoverable:
        raise HTTPException(404, "Кандидат недоступен для предложений")
    cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == candidate.id))
    median = await role_median(db, cat.primary_role if cat else None, cat.grade if cat else None)
    return {"salary_hint": salary_gap_hint(body.salary_to_gross, candidate.salary_from_gross),
            "market_flag": market_flag(body.salary_from_gross, body.salary_to_gross, median),
            "market_median": median}


@router.get("/market")
async def offer_market(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    """Decline shares and salary quartiles. A cell with fewer than five people is omitted."""
    if await db.get(Employer, _eid(current)) is None:
        raise HTTPException(404, "Работодатель не найден")
    reasons = list(await db.scalars(select(Offer.decline_reason).where(Offer.status == "rejected")))
    rows = (await db.execute(
        select(CategoryAssignment.primary_role, CategoryAssignment.grade, Participant.salary_from_gross)
        .join(Participant, Participant.id == CategoryAssignment.participant_id)
        .where(Participant.salary_from_gross.is_not(None), Participant.deleted_at.is_(None),
               Participant.is_visible.is_(True)))).all()
    buckets: dict[tuple[str, str], list[int]] = {}
    for role, grade, amount in rows:
        if role and grade and amount:
            buckets.setdefault((role, grade), []).append(int(amount))
    salaries = []
    for (role, grade), amounts in sorted(buckets.items()):
        cell = quartiles(amounts)
        if cell:
            salaries.append({"role": role, "grade": grade, **cell})
    return {"reasons": reason_shares(list(reasons)), "salaries": salaries}


@router.post("/", status_code=201)
async def create_offer(body: OfferCreate, current: dict = Depends(get_current_employer),
                       db: AsyncSession = Depends(get_db),
                       idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    scope = f"offer:{current['sub']}"
    digest = fingerprint(body.model_dump(mode="json"))
    try:
        stored = await idem_begin(scope, idempotency_key, digest)
    except IdempotencyConflict as e:
        raise HTTPException(409, e.message) from e
    except IdempotencyUnavailable as e:
        raise HTTPException(503, "Повтор запроса сейчас невозможен") from e
    if stored:
        return JSONResponse(stored["body"], status_code=stored["status"])
    try:
        payload = await _create_offer(body, current, db)
    except Exception:
        await idem_abort(scope, idempotency_key)
        raise
    try:
        await idem_finish(scope, idempotency_key, digest, 201, payload)
    except IdempotencyUnavailable as e:
        raise HTTPException(503, "Повтор запроса сейчас невозможен") from e
    return payload


async def _create_offer(body: OfferCreate, current: dict, db: AsyncSession) -> dict:
    employer = await db.get(Employer, _eid(current))
    if not employer:
        raise HTTPException(404, "Работодатель не найден")
    if getattr(employer, "invites_paused_at", None) is not None:
        raise ApiError(403, "invites_paused", "Приглашения приостановлены до проверки")
    candidate = await db.get(Participant, body.candidate_id)
    if not candidate or not candidate.discoverable:
        raise HTTPException(404, "Кандидат недоступен для предложений")
    pending = await db.scalar(select(Offer).where(
        Offer.employer_id == employer.id, Offer.candidate_id == candidate.id, Offer.status == "pending"))
    if pending and expire_if_stale(pending):
        await db.flush()
        pending = None
    if pending:
        raise HTTPException(409, "Активный оффер этому кандидату уже есть")
    declined = list(await db.scalars(select(Offer).where(
        Offer.employer_id == employer.id, Offer.candidate_id == candidate.id, Offer.status == "rejected")))
    pause = reinvite_after(declined)
    if pause:
        raise ApiError(409, "decline_pause",
                       f"Кандидат отклонил ваше приглашение. Повторно пригласить можно после {pause:%d.%m.%Y}",
                       details={"reinvite_after": pause.isoformat()})
    # Count only an invitation that passed the checks. A 404 or 409 must not spend the daily cap.
    # Redis down refuses the invite instead of opening the cap.
    try:
        level = trust_level(employer)
        cap = invite_limit(level)
        if await too_many(f"offers:create:{employer.id}", limit=cap, window_seconds=86_400, fail_closed=True):
            raise HTTPException(429, f"Лимит приглашений на сегодня исчерпан ({cap}). {next_step(level)}")
    except RateLimitUnavailable as e:
        raise HTTPException(503, "Лимит приглашений сейчас недоступен") from e
    offer = Offer(
        employer_id=employer.id, candidate_id=candidate.id,
        salary_from_gross=body.salary_from_gross, salary_to_gross=body.salary_to_gross,
        currency=body.currency, role=body.role, work_format=body.work_format, message=body.message,
        contact_method=body.contact_method.strip(), perks=body.perks,
        practice_stage="sent" if body.practice else None,
        status="pending", expires_at=datetime.now(UTC) + timedelta(days=14),
    )
    db.add(offer)
    try:
        # uq_offers_pending_pair (migration 0002) closes the check-then-insert race.
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(409, "Активный оффер этому кандидату уже есть") from e
    cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == candidate.id))
    median = await role_median(db, cat.primary_role if cat else None, cat.grade if cat else None)
    flag = market_flag(offer.salary_from_gross, offer.salary_to_gross, median)
    if flag:
        db.add(OfferFlag(offer_id=offer.id, flag=flag, company_name=employer.company_name, role_title=offer.role,
                         salary_from_gross=offer.salary_from_gross, salary_to_gross=offer.salary_to_gross))
    outbox = Outbox()
    await notify(db, outbox, "participant", candidate.id, "offer_new",
                 f"Приглашение от «{employer.company_name}»",
                 f"{employer.company_name} приглашает на роль «{offer.role}»: "
                 f"{salary(offer.salary_from_gross, offer.salary_to_gross)}. "
                 "Контакты компания получит, только если вы примете приглашение. Срок ответа — 14 дней.",
                 "/candidate/offers")
    await db.commit()
    from app.services.search.cache import publish_invite
    await publish_invite()
    await outbox.deliver()
    out = _offer_out(offer)
    out["salary_hint"] = salary_gap_hint(offer.salary_to_gross, candidate.salary_from_gross)
    out["market_flag"] = flag
    return out


class PracticeIn(BaseModel):
    stage: Literal["screening", "trial", "hired", "closed"]


@router.post("/{offer_id}/practice")
async def advance_practice(offer_id: uuid.UUID, body: PracticeIn, current: dict = Depends(get_current_employer),
                           db: AsyncSession = Depends(get_db)):
    """Move an internship invitation one step. The match score and the grade stay put."""
    offer = await db.get(Offer, offer_id)
    if offer is None or offer.employer_id != _eid(current) or offer.practice_stage is None:
        raise ApiError(404, "not_found", "Практики по этому приглашению нет")
    try:
        offer.practice_stage = next_stage(offer.practice_stage, body.stage)
    except ValueError:
        raise ApiError(409, "conflict", "Этап практики можно сдвинуть только на следующий") from None
    await db.commit()
    return _offer_out(offer)


@router.get("/")
async def list_my_offers(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(
        select(Offer).where(Offer.employer_id == _eid(current)).order_by(Offer.created_at.desc())))
    if expire_stale(rows):
        await db.commit()
    # The list shows whom each invitation went to: the anonymous category, not a name.
    cats = {c.participant_id: c for c in await db.scalars(select(CategoryAssignment).where(
        CategoryAssignment.participant_id.in_([o.candidate_id for o in rows])))} if rows else {}
    unread = await unread_counts(db, [o.id for o in rows if o.status == "accepted"], "employer")
    out = []
    for o in rows:
        card = _offer_out(o)
        card["unread_messages"] = unread.get(o.id, 0)
        cat = cats.get(o.candidate_id)
        card["candidate"] = (
            {"role": cat.primary_role, "grade": cat.grade, "grade_source": cat.grade_source, "label": None}
            if cat else {"role": None, "grade": None, "grade_source": None, "label": "Кандидат"})
        out.append(card)
    return out


@router.post("/{offer_id}/withdraw")
async def withdraw_offer(offer_id: uuid.UUID, current: dict = Depends(get_current_employer),
                         db: AsyncSession = Depends(get_db)):
    # Same lock as the candidate side: withdraw and accept cannot both win.
    offer = await db.get(Offer, offer_id, with_for_update=True)
    if not offer or offer.employer_id != _eid(current):
        raise HTTPException(404, "Оффер не найден")
    if offer.status != "pending":
        raise HTTPException(409, "Отозвать можно только ожидающий оффер")
    offer.status = "withdrawn"
    employer = await db.get(Employer, offer.employer_id)
    outbox = Outbox()
    await notify(db, outbox, "participant", offer.candidate_id, "offer_withdrawn",
                 f"«{employer.company_name}» отозвала приглашение",
                 f"Приглашение на роль «{offer.role}» больше не действует.", "/candidate/offers")
    await db.commit()
    from app.services.search.cache import publish_invite
    await publish_invite()
    await outbox.deliver()
    return {"status": offer.status}


@router.get("/{offer_id}/contacts")
async def reveal_contacts(offer_id: uuid.UUID, current: dict = Depends(get_current_employer),
                          db: AsyncSession = Depends(get_db)):
    offer = await db.get(Offer, offer_id)
    if not offer or offer.employer_id != _eid(current):
        raise HTTPException(404, "Оффер не найден")
    if offer.status != "accepted":
        raise HTTPException(403, "Контакты открываются только после согласия кандидата")
    if offer.contacts_revoked_at is not None:
        db.add(AccessLog(employer_id=offer.employer_id, participant_id=offer.candidate_id,
                         access_type="contacts_denied_revoked"))
        await db.commit()
        raise ApiError(403, "contacts_revoked")
    candidate = await db.get(Participant, offer.candidate_id)
    if not candidate:
        raise HTTPException(404, "Кандидат не найден")
    if not await contacts_allowed(db, candidate):
        raise ApiError(403, "consent_withdrawn")
    now = datetime.now(UTC)
    if offer.contacts_revealed_at is None:
        offer.contacts_revealed_at = now
    db.add(AccessLog(employer_id=offer.employer_id, participant_id=candidate.id, access_type="contacts_view"))
    await db.commit()
    return {
        "candidate_id": str(candidate.id), "display_name": candidate.display_name,
        "email": candidate.email, "telegram": candidate.telegram,
        "phone": candidate.phone, "region": candidate.region,
        "contacts_revealed_at": offer.contacts_revealed_at.isoformat(),
    }
