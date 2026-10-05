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

from app.items.registry import BLUEPRINTS, families_for
from app.models import Participant, PracticeAttempt, Vacancy
from app.services.vacancy_exam import GRADE_LEVEL, TOPIC_LABELS, form_exam


def public_attempt(row: PracticeAttempt) -> dict:
    """What the client may see before the answer is checked."""
    return {
        "id": str(row.id),
        "topic": row.topic,
        "topic_label": TOPIC_LABELS.get(row.topic, row.topic),
        "stem": row.stem,
        "code": row.code,
        "language": row.language,
        "options": [{"index": i, "text": text} for i, text in enumerate(row.options)],
        "answered": row.answered_at is not None,
    }


def _pick_family(spec: str, topic: str | None):
    code = [f for f in families_for(spec) if f.kind == "code"]
    if topic:
        matched = [f for f in code if f.topic == topic]
        if matched:
            return matched[0]
    return code[0] if code else None


async def start_practice(db: AsyncSession, participant: Participant,
                         vacancy_id: uuid.UUID | None = None) -> PracticeAttempt:
    open_row = await db.scalar(select(PracticeAttempt).where(
        PracticeAttempt.participant_id == participant.id, PracticeAttempt.answered_at.is_(None)))
    if open_row is not None:
        return open_row
    spec = participant.specialization or "backend"
    if spec not in BLUEPRINTS:
        spec = "backend"
    grade = participant.declared_grade if participant.declared_grade in GRADE_LEVEL else "middle"
    topic = None
    stored_vacancy = None
    if vacancy_id is not None:
        vacancy = await db.get(Vacancy, vacancy_id)
        if vacancy is None or not vacancy.is_open:
            raise LookupError("vacancy")
        exam = form_exam(vacancy.title, vacancy.description or "", list(vacancy.skills or []),
                         vacancy.role, vacancy.grade)
        spec = exam["specialization"]
        topic = exam["topics"][0]["topic"] if exam["topics"] else None
        stored_vacancy = vacancy.id
        if exam["target_grade"] in GRADE_LEVEL:
            grade = exam["target_grade"]
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
                          answer_index: int) -> dict:
    row = await db.get(PracticeAttempt, attempt_id)
    if row is None or row.participant_id != participant.id:
        raise LookupError("attempt")
    if row.answered_at is None:
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
