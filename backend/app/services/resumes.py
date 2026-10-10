"""Up to three resumes per candidate: the survey specialization and two more.

Each extra resume is a specialization with a declared grade, a stack and a short note. Search by that
specialization finds the person with this grade marked as not confirmed; a test passed in the same
specialization outranks it. The note is free text that an employer reads before any invitation, so a
name or a contact in it is refused.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateResume, Participant
from app.services.ai.assistant import has_identity
from app.services.categorization import GRADES
from app.services.skills import normalize_skill
from app.services.survey import SPECIALIZATIONS

EXTRA_MAX = 2
STACK_MAX = 15
SUMMARY_MAX = 600


@dataclass(frozen=True)
class ResumeDraft:
    specialization: str
    grade: str
    stack: list[str]
    summary: str | None


def clean(raw_spec: str, raw_grade: str, raw_stack: list[str], raw_summary: str | None,
          primary: str | None) -> ResumeDraft:
    """Check one resume. Raises ValueError with the text to show."""
    spec = (raw_spec or "").strip()
    if spec not in SPECIALIZATIONS:
        raise ValueError("Специализацию выберите из списка")
    if primary and spec == primary:
        raise ValueError("Эта специализация уже указана в опросе")
    grade = (raw_grade or "").strip()
    if grade not in GRADES:
        raise ValueError("Грейд выберите из списка")
    stack: list[str] = []
    for item in raw_stack or []:
        name = normalize_skill(item) or (item or "").strip()
        if name and name not in stack:
            stack.append(name[:40])
    if len(stack) > STACK_MAX:
        raise ValueError(f"Не больше {STACK_MAX} технологий")
    summary = (raw_summary or "").strip() or None
    if summary and len(summary) > SUMMARY_MAX:
        raise ValueError(f"Описание длиннее {SUMMARY_MAX} символов")
    if summary and has_identity(summary):
        raise ValueError("В описании не должно быть имени и контактов: их откроет только принятое приглашение")
    return ResumeDraft(spec, grade, stack, summary)


async def extras(db: AsyncSession, participant_id: uuid.UUID) -> list[CandidateResume]:
    return list(await db.scalars(select(CandidateResume).where(CandidateResume.participant_id == participant_id)
                                 .order_by(CandidateResume.created_at)))


def out(row: CandidateResume) -> dict:
    return {"id": str(row.id), "specialization": row.specialization,
            "label": SPECIALIZATIONS.get(row.specialization, row.specialization),
            "grade": row.grade, "stack": list(row.stack or []), "summary": row.summary,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None}


def primary_out(p: Participant, assessed: str | None) -> dict | None:
    if not p.specialization:
        return None
    return {"id": None, "specialization": p.specialization,
            "label": SPECIALIZATIONS.get(p.specialization, p.specialization),
            "grade": assessed or p.declared_grade, "grade_source": "assessed" if assessed else "declared",
            "primary": True}
