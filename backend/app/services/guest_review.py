"""A hiring manager opens an anonymized shortlist without an account.

The link keeps a snapshot of the first ten visible cards. Names, contacts and
the candidate id stay off that snapshot. Marks do not change the search order.
"""
from __future__ import annotations

import hashlib
import secrets

SEAT_LIMIT = 10
TTL_DAYS = 7
MARKS = frozenset({"yes", "no", "later"})


def _lines(value: object, limit: int, width: int = 240) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip()[:width])
        if len(out) >= limit:
            break
    return out


def public_seats(cards: list[dict]) -> tuple[list[dict], list[str]]:
    """Public rows and the private ids in the same order. The public rows have no id."""
    seats: list[dict] = []
    ids: list[str] = []
    for index, card in enumerate(cards[:SEAT_LIMIT], start=1):
        if not isinstance(card, dict):
            card = {}
        seats.append({
            "seat": index,
            "role": card.get("role") if isinstance(card.get("role"), str) else None,
            "grade": card.get("grade") if isinstance(card.get("grade"), str) else None,
            "grade_source": card.get("grade_source") if isinstance(card.get("grade_source"), str) else None,
            "region": card.get("region") if isinstance(card.get("region"), str) else None,
            "stack": _lines(card.get("stack"), 12, 80),
            "matched_skills": _lines(card.get("matched_skills"), 12, 80),
            "missing_skills": _lines(card.get("missing_skills"), 12, 80),
            "why": _lines(card.get("why"), 8),
        })
        raw = card.get("candidate_id")
        ids.append(raw if isinstance(raw, str) else "")
    return seats, ids


def fresh_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(24)
    return token, hashlib.sha256(token.encode()).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def apply_mark(marks: dict | None, seat_count: int, seat: int, mark: str) -> dict:
    if mark not in MARKS or not 1 <= seat <= seat_count:
        raise ValueError("mark")
    out = {str(key): value for key, value in (marks or {}).items() if value in MARKS}
    out[str(seat)] = mark
    return out


def marks_for_owner(seat_ids: list[str], marks: dict | None) -> list[dict]:
    """Marks the company can attach to its own cards. Empty ids are dropped."""
    out = []
    for index, pid in enumerate(seat_ids, start=1):
        mark = (marks or {}).get(str(index))
        if isinstance(pid, str) and pid and mark in MARKS:
            out.append({"candidate_id": pid, "mark": mark})
    return out
