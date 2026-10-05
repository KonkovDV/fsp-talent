"""Tell the other side of a hiring step that it is their move: a row for the bell and a letter.

Letters never carry the other side's personal data. Before the candidate accepts, the employer sees
only the anonymous category; the candidate sees the company, the role and the salary range.
The row is written inside the caller's transaction; the letter goes out after the commit (`deliver`),
so a rolled-back request does not send mail.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Employer, Notification, Participant
from app.services.mail import send_mail


@dataclass
class Outbox:
    letters: list[tuple[str, str, str]] = field(default_factory=list)

    async def deliver(self) -> None:
        for to, subject, text in self.letters:
            await send_mail(to, subject, text, meta={"purpose": "notification"})
        self.letters.clear()


def _rub(value: int | None) -> str:
    return f"{value:,}".replace(",", " ") if value is not None else "—"


def salary(lo: int | None, hi: int | None) -> str:
    return f"{_rub(lo)}–{_rub(hi)} ₽ до вычета НДФЛ"


async def notify(db: AsyncSession, outbox: Outbox, role: str, recipient_id: uuid.UUID, kind: str,
                 title: str, body: str, link: str) -> None:
    db.add(Notification(recipient_role=role, recipient_id=recipient_id, kind=kind, title=title, body=body,
                        link=link))
    model = Participant if role == "participant" else Employer
    person = await db.get(model, recipient_id)
    email = getattr(person, "email", None)
    if email and getattr(person, "deleted_at", None) is None:
        url = settings.PUBLIC_BASE_URL.rstrip("/") + link
        outbox.letters.append((email, f"ФСП Талант: {title}", f"{body}\n\nОткрыть: {url}\n"))


def category_label(role: str | None, grade: str | None) -> str:
    from app.services.survey import SPECIALIZATIONS
    if not role:
        return "кандидат без категории"
    return f"{SPECIALIZATIONS.get(role, role)}, {grade}" if grade else SPECIALIZATIONS.get(role, role)
