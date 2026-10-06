"""One short task formed the same way as the grade test, without changing the grade.

Taken from the strongest competitor's idea (a task built from the vacancy's requirements,
or a voluntary drill on the specialization) and implemented on our parametric families.
The right answer stays on the server until the candidate submits.
"""
from __future__ import annotations

import random
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.items import same_number, whole_number
from app.items.registry import BLUEPRINTS, families_for
from app.models import Participant, PracticeAttempt, Vacancy
from app.services.vacancy_exam import GRADE_LEVEL, TOPIC_LABELS, form_exam


def _typed(row: PracticeAttempt) -> bool:
    return whole_number(str(row.options[row.correct_index]))


def public_attempt(row: PracticeAttempt) -> dict:
    """What the client may see before the answer is checked.

    A whole-number answer is typed. Listing it among four options would put the right value on screen.
    """
    typed = _typed(row)
    return {
        "id": str(row.id),
        "topic": row.topic,
        "topic_label": TOPIC_LABELS.get(row.topic, row.topic),
        "stem": row.stem,
        "code": row.code,
        "language": row.language,
        "answer_mode": "number" if typed else "choice",
        "options": [] if typed else [{"index": i, "text": text} for i, text in enumerate(row.options)],
        "answered": row.answered_at is not None,
    }


def same_practice_request(open_topic: str, open_vacancy: uuid.UUID | None,
                          asked_topic: str | None, asked_vacancy: uuid.UUID | None) -> bool:
    """An unfinished task is reused only for the same request.

    A link from a weak topic, or a button on another vacancy, must not receive the task that was already open.
    """
    if asked_vacancy is not None:
        return open_vacancy == asked_vacancy
    if asked_topic:
        return open_vacancy is None and open_topic == asked_topic
    return True


def resolve_practice_topic(asked: str | None, vacancy_topic: str | None, *, from_vacancy: bool) -> str | None:
    """The topic the candidate asked for. A vacancy's own topic wins over that request."""
    if from_vacancy:
        return vacancy_topic if vacancy_topic in TOPIC_LABELS else None
    return asked if asked in TOPIC_LABELS else None


def _pick_family(spec: str, topic: str | None):
    code = [f for f in families_for(spec) if f.kind == "code"]
    if topic:
        matched = [f for f in code if f.topic == topic]
        if matched:
            return matched[0]
    return code[0] if code else None


async def start_practice(db: AsyncSession, participant: Participant,
                         vacancy_id: uuid.UUID | None = None, topic: str | None = None) -> PracticeAttempt:
    open_rows = list(await db.scalars(select(PracticeAttempt).where(
        PracticeAttempt.participant_id == participant.id, PracticeAttempt.answered_at.is_(None))
        .order_by(PracticeAttempt.created_at.desc())))
    match = next((row for row in open_rows
                  if same_practice_request(row.topic, row.vacancy_id, topic, vacancy_id)), None)
    for row in open_rows:
        if row is not match:
            await db.delete(row)
    if match is not None:
        await db.flush()
        return match
    if open_rows:
        await db.flush()
    spec = participant.specialization or "backend"
    if spec not in BLUEPRINTS:
        spec = "backend"
    grade = participant.declared_grade if participant.declared_grade in GRADE_LEVEL else "middle"
    asked = topic
    stored_vacancy = None
    if vacancy_id is not None:
        vacancy = await db.get(Vacancy, vacancy_id)
        if vacancy is None or not vacancy.is_open:
            raise LookupError("vacancy")
        exam = form_exam(vacancy.title, vacancy.description or "", list(vacancy.skills or []),
                         vacancy.role, vacancy.grade)
        spec = exam["specialization"]
        vacancy_topic = exam["topics"][0]["topic"] if exam["topics"] else None
        topic = resolve_practice_topic(asked, vacancy_topic, from_vacancy=True)
        stored_vacancy = vacancy.id
        if exam["target_grade"] in GRADE_LEVEL:
            grade = exam["target_grade"]
    else:
        topic = resolve_practice_topic(asked, None, from_vacancy=False)
    family = _pick_family(spec, topic)
    if family is None:
        raise LookupError("family")
    level = GRADE_LEVEL.get(grade, 3)
    if not family.available(spec, level):
        level = next(lv for lv in family.levels if family.available(spec, lv))
    item = family.generate(random.Random(secrets.token_hex(8)), level, spec)
    row = PracticeAttempt(
        participant_id=participant.id, vacancy_id=stored_vacancy, topic=family.topic, family_id=family.id,
        stem=item.stem, code=item.code, language=item.language, options=item.options,
        correct_index=item.correct, explanation=item.explanation, created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row


async def answer_practice(db: AsyncSession, participant: Participant, attempt_id: uuid.UUID,
                          answer_index: int | None = None, answer_text: str | None = None) -> dict:
    row = await db.get(PracticeAttempt, attempt_id)
    if row is None or row.participant_id != participant.id:
        raise LookupError("attempt")
    if row.answered_at is None:
        if _typed(row):
            if not (answer_text or "").strip():
                raise ValueError("answer")
            row.is_correct = same_number(answer_text or "", str(row.options[row.correct_index]))
        else:
            if answer_index is None or not 0 <= answer_index < len(row.options):
                raise ValueError("answer")
            row.answer_index = answer_index
            row.is_correct = answer_index == row.correct_index
        row.answered_at = datetime.now(UTC)
        participant.practice_topic = row.topic
        participant.practice_ok = row.is_correct
        participant.practice_at = row.answered_at
        await db.flush()
    return {
        **public_attempt(row),
        "is_correct": row.is_correct,
        "explanation": row.explanation,
    }
