"""Times for a meeting after the candidate accepted, and the calendar file both sides download.

Times are stored as an instant and written into the file as Moscow wall time.
No external calendar is called.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")
FORMAT_RU = {"online": "онлайн", "office": "в офисе", "phone": "по телефону"}


def still_ahead(starts_at: datetime, now: datetime | None = None) -> bool:
    """The meeting can still be chosen. A naive instant is read as UTC."""
    moment = now or datetime.now(UTC)
    start = starts_at if starts_at.tzinfo is not None else starts_at.replace(tzinfo=UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return start > moment


def moscow_start(day: str, clock: str) -> datetime:
    """Wall clock in Moscow. `day` is YYYY-MM-DD, `clock` is HH:MM."""
    wall = datetime.fromisoformat(f"{day}T{clock}")
    if wall.tzinfo is not None:
        raise ValueError("time is already zoned")
    return wall.replace(tzinfo=MSK)


def _escape(text: str) -> str:
    """Keep a user string inside one calendar line. A raw break would start a second event."""
    return (
        text.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def calendar_text(slot_id: uuid.UUID, starts_at: datetime, meeting_format: str, place: str | None,
                  summary: str) -> str:
    """One event, RFC 5545. DTSTART carries the Moscow zone name, not a UTC stamp."""
    local = starts_at.astimezone(MSK)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    start = local.strftime("%Y%m%dT%H%M%S")
    desc = f"Формат: {FORMAT_RU.get(meeting_format, meeting_format)}"
    if place:
        desc = desc + "\\n" + _escape(place)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//FSP Talent//Interview//RU",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{slot_id}@fsp-talent",
        f"DTSTAMP:{stamp}",
        f"DTSTART;TZID=Europe/Moscow:{start}",
        "DURATION:PT1H",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{desc}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def slot_view(row) -> dict:
    local = row.starts_at.astimezone(MSK)
    return {
        "id": str(row.id),
        "date": local.date().isoformat(),
        "time": local.strftime("%H:%M"),
        "format": row.format,
        "place": row.place,
        "chosen": bool(row.chosen),
        "outcome": row.outcome,
    }
