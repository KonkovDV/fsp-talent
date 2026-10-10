"""Meeting times after an accepted invitation. Both sides download one calendar file.

The employer offers one to three Moscow times. The candidate picks one. The employer
then records passed, failed or no-show. That outcome changes P(accept) of the next
invitation from the same company. No external calendar is called.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_any_auth
from app.api.errors import ApiError
from app.core.database import get_db
from app.models import Employer, InterviewCode, InterviewSlot, Offer, Participant
from app.models.interview import FORMATS, OUTCOMES
from app.services.code_lab import problem_ids, problem_public
from app.services.interview_code import CodeStale, apply_code_draft, code_view
from app.services.interviews import MSK, calendar_text, moscow_start, slot_view, still_ahead
from app.services.notify import Outbox, notify
from app.services.search.cache import bump_bank_epoch

router = APIRouter(prefix="/offers", tags=["interviews"])


class SlotIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    format: str = Field(pattern="^(online|office|phone)$")
    place: str | None = Field(None, max_length=300)


class SlotsIn(BaseModel):
    slots: list[SlotIn] = Field(min_length=1, max_length=3)


class OutcomeIn(BaseModel):
    outcome: str = Field(pattern="^(passed|failed|no_show)$")


async def _offer(db: AsyncSession, offer_id: uuid.UUID, current: dict) -> tuple[Offer, str]:
    offer = await db.get(Offer, offer_id)
    subject = uuid.UUID(current["sub"])
    role = current.get("role")
    side = None
    if offer is not None and role == "participant" and offer.candidate_id == subject:
        side = "participant"
    if offer is not None and role == "employer" and offer.employer_id == subject:
        side = "employer"
    if offer is None or side is None:
        raise ApiError(404, "not_found", "Приглашение не найдено")
    if offer.status != "accepted":
        raise ApiError(409, "conflict", "Собеседование предлагают после принятия приглашения")
    return offer, side


async def _rows(db: AsyncSession, offer_id: uuid.UUID) -> list[InterviewSlot]:
    return list(await db.scalars(
        select(InterviewSlot).where(InterviewSlot.offer_id == offer_id).order_by(InterviewSlot.starts_at)))


@router.get("/{offer_id}/slots")
async def list_slots(offer_id: uuid.UUID, current: dict = Depends(get_any_auth),
                     db: AsyncSession = Depends(get_db)):
    offer, _side = await _offer(db, offer_id, current)
    rows = await _rows(db, offer.id)
    chosen = next((row for row in rows if row.chosen), None)
    return {"slots": [slot_view(row) for row in rows], "outcome": chosen.outcome if chosen else None}


@router.post("/{offer_id}/slots")
async def propose_slots(offer_id: uuid.UUID, body: SlotsIn, current: dict = Depends(get_any_auth),
                        db: AsyncSession = Depends(get_db)):
    offer, side = await _offer(db, offer_id, current)
    if side != "employer":
        raise ApiError(403, "forbidden", "Время предлагает компания")
    if offer.contacts_revoked_at is not None:
        raise ApiError(403, "contacts_revoked", "Кандидат закрыл контакты для компании")
    rows = await _rows(db, offer.id)
    if any(row.chosen for row in rows):
        raise ApiError(409, "conflict", "Кандидат уже выбрал время")
    now = datetime.now(UTC)
    built = []
    seen = set()
    for item in body.slots:
        try:
            start = moscow_start(item.date, item.time)
        except ValueError as exc:
            raise ApiError(422, "validation_error", "Дата или время указаны неверно") from exc
        if start <= now:
            raise ApiError(422, "validation_error", "Время собеседования уже прошло")
        if item.format not in FORMATS:
            raise ApiError(422, "validation_error", "Формат: онлайн, офис или телефон")
        if start in seen:
            raise ApiError(422, "validation_error", "Одно и то же время указано дважды")
        seen.add(start)
        built.append((start, item.format, (item.place or "").strip() or None))
    for row in rows:
        await db.delete(row)
    for start, meeting_format, place in built:
        db.add(InterviewSlot(offer_id=offer.id, starts_at=start, format=meeting_format, place=place))
    company = await db.get(Employer, offer.employer_id)
    name = company.company_name if company is not None else "Компания"
    outbox = Outbox()
    await notify(db, outbox, "participant", offer.candidate_id, "interview_slots",
                 f"{name} предлагает время собеседования",
                 "Откройте приглашение и выберите один из слотов. Файл календаря скачивается там же.",
                 "/candidate/offers")
    await db.commit()
    await outbox.deliver()
    fresh = await _rows(db, offer.id)
    return {"slots": [slot_view(row) for row in fresh]}


@router.post("/{offer_id}/slots/{slot_id}/choose")
async def choose_slot(offer_id: uuid.UUID, slot_id: uuid.UUID, current: dict = Depends(get_any_auth),
                      db: AsyncSession = Depends(get_db)):
    offer, side = await _offer(db, offer_id, current)
    if side != "participant":
        raise ApiError(403, "forbidden", "Время выбирает кандидат")
    rows = await _rows(db, offer.id)
    target = next((row for row in rows if row.id == slot_id), None)
    if target is None:
        raise ApiError(404, "not_found", "Такого времени нет")
    if not still_ahead(target.starts_at):
        raise ApiError(422, "validation_error", "Это время уже прошло")
    if any(row.chosen and row.id != target.id for row in rows):
        raise ApiError(409, "conflict", "Время уже выбрано")
    for row in rows:
        row.chosen = row.id == target.id
    person = await db.get(Participant, offer.candidate_id)
    who = person.display_name if person is not None else "Кандидат"
    local = target.starts_at.astimezone(MSK)
    outbox = Outbox()
    await notify(db, outbox, "employer", offer.employer_id, "interview_chosen",
                 f"{who} выбрал время собеседования",
                 f"Встреча {local.strftime('%d.%m.%Y %H:%M')} по Москве. Файл календаря — в приглашении.",
                 "/employer/offers")
    await db.commit()
    await outbox.deliver()
    return {"slots": [slot_view(row) for row in await _rows(db, offer.id)]}


@router.get("/{offer_id}/interview.ics")
async def download_calendar(offer_id: uuid.UUID, current: dict = Depends(get_any_auth),
                            db: AsyncSession = Depends(get_db)):
    offer, _side = await _offer(db, offer_id, current)
    rows = await _rows(db, offer.id)
    chosen = next((row for row in rows if row.chosen), None)
    if chosen is None:
        raise ApiError(404, "not_found", "Сначала выберите время")
    company = await db.get(Employer, offer.employer_id)
    name = company.company_name if company is not None else "компания"
    body = calendar_text(chosen.id, chosen.starts_at, chosen.format, chosen.place,
                         f"Собеседование: {offer.role}, {name}")
    return Response(content=body, media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="interview-{offer.id}.ics"'})


@router.post("/{offer_id}/interview/outcome")
async def set_outcome(offer_id: uuid.UUID, body: OutcomeIn, current: dict = Depends(get_any_auth),
                      db: AsyncSession = Depends(get_db)):
    offer, side = await _offer(db, offer_id, current)
    if side != "employer":
        raise ApiError(403, "forbidden", "Итог записывает компания")
    if body.outcome not in OUTCOMES:
        raise ApiError(422, "validation_error", "Итог: прошёл, не прошёл или не пришёл")
    rows = await _rows(db, offer.id)
    chosen = next((row for row in rows if row.chosen), None)
    if chosen is None:
        raise ApiError(409, "conflict", "Кандидат ещё не выбрал время")
    chosen.outcome = body.outcome
    chosen.outcome_at = datetime.now(UTC)
    await db.commit()
    await bump_bank_epoch()
    return {"outcome": chosen.outcome}


class OpenCodeIn(BaseModel):
    problem_id: str | None = Field(None, max_length=40)
    prompt: str = Field("", max_length=4000)


class CodeDraftIn(BaseModel):
    text: str = Field(max_length=8000)
    version: int = Field(ge=0)


class CodeDisputeIn(BaseModel):
    text: str = Field(min_length=10, max_length=2000)


def _code_out(row: InterviewCode) -> dict:
    problem = problem_public(row.problem_id) if row.problem_id else None
    return code_view(problem, row.prompt or "", row.draft or "", row.draft_version or 0,
                     list(row.snapshots or []), row.dispute)


@router.post("/{offer_id}/code", status_code=201)
async def open_code(offer_id: uuid.UUID, body: OpenCodeIn, current: dict = Depends(get_any_auth),
                    db: AsyncSession = Depends(get_db)):
    """A library problem or a written prompt. No model is called."""
    offer, side = await _offer(db, offer_id, current)
    if side != "employer":
        raise ApiError(403, "forbidden", "Задание даёт компания")
    pid = (body.problem_id or "").strip() or None
    if pid is not None and pid not in set(problem_ids()):
        raise ApiError(422, "validation_error", "Такого задания в библиотеке нет")
    prompt = body.prompt.strip()
    if pid is None and len(prompt) < 20:
        raise ApiError(422, "validation_error", "Напишите условие или выберите задание из библиотеки")
    existing = await db.scalar(select(InterviewCode.id).where(InterviewCode.offer_id == offer.id))
    if existing is not None:
        raise ApiError(409, "conflict", "Задание уже есть")
    row = InterviewCode(offer_id=offer.id, problem_id=pid, prompt=prompt, draft="", draft_version=0,
                        snapshots=[], created_at=datetime.now(UTC))
    db.add(row)
    await db.commit()
    return _code_out(row)


@router.get("/{offer_id}/code")
async def get_code(offer_id: uuid.UUID, current: dict = Depends(get_any_auth),
                   db: AsyncSession = Depends(get_db)):
    offer, _side = await _offer(db, offer_id, current)
    row = await db.scalar(select(InterviewCode).where(InterviewCode.offer_id == offer.id))
    if row is None:
        raise ApiError(404, "not_found", "Задания пока нет")
    return _code_out(row)


@router.put("/{offer_id}/code")
async def save_code(offer_id: uuid.UUID, body: CodeDraftIn, current: dict = Depends(get_any_auth),
                    db: AsyncSession = Depends(get_db)):
    offer, side = await _offer(db, offer_id, current)
    if side != "participant":
        raise ApiError(403, "forbidden", "Черновик пишет кандидат")
    row = await db.scalar(select(InterviewCode).where(InterviewCode.offer_id == offer.id))
    if row is None:
        raise ApiError(404, "not_found", "Задания пока нет")
    try:
        version, text, shots = apply_code_draft(
            row.draft_version or 0, body.version, body.text, list(row.snapshots or []))
    except CodeStale:
        raise ApiError(409, "conflict", "Черновик уже новее: обновите страницу") from None
    row.draft_version, row.draft, row.snapshots = version, text, shots
    await db.commit()
    return _code_out(row)


@router.post("/{offer_id}/code/dispute")
async def dispute_code(offer_id: uuid.UUID, body: CodeDisputeIn, current: dict = Depends(get_any_auth),
                       db: AsyncSession = Depends(get_db)):
    """A note about the task. The grade and the match score stay as they were."""
    offer, side = await _offer(db, offer_id, current)
    if side != "participant":
        raise ApiError(403, "forbidden", "Пометку пишет кандидат")
    row = await db.scalar(select(InterviewCode).where(InterviewCode.offer_id == offer.id))
    if row is None or not (row.draft_version or 0):
        raise ApiError(409, "conflict", "Сначала сохраните черновик")
    row.dispute = body.text.strip()
    await db.commit()
    return _code_out(row)
