"""Allowed moves of an invitation.

Pending can be accepted, declined, withdrawn or expired. A later state does not go back.
The table is the one place that decides; callers do not assign status themselves.

A "yes, if" answer stays pending. It records the condition and does not open contacts.
"""
from __future__ import annotations

from datetime import UTC, datetime

TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"accepted", "rejected", "withdrawn", "expired"}),
}
COUNTER_MIN = 8
COUNTER_MAX = 280


class IllegalOfferMove(ValueError):
    """The invitation is not in a state that allows this move."""


def can_move(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, frozenset())


def move_offer(offer, target: str) -> None:
    if not can_move(getattr(offer, "status", ""), target):
        raise IllegalOfferMove(f"{getattr(offer, 'status', None)} -> {target}")
    offer.status = target


def record_counter(offer, note: str) -> str:
    """Keep the invitation pending and store the candidate's condition.

    Contacts stay closed and the list order does not read this note.
    """
    if getattr(offer, "status", "") != "pending":
        raise IllegalOfferMove(f"{getattr(offer, 'status', None)} stays put")
    text = " ".join((note or "").split())
    if not COUNTER_MIN <= len(text) <= COUNTER_MAX:
        raise ValueError("condition")
    offer.counter_note = text
    offer.counter_at = datetime.now(UTC)
    return text


def accept_counter(offer) -> str:
    """The company agrees to the written condition. Contacts open. Search order does not read the note."""
    if getattr(offer, "status", "") != "pending":
        raise IllegalOfferMove(f"{getattr(offer, 'status', None)} stays put")
    note = " ".join((getattr(offer, "counter_note", None) or "").split())
    if not COUNTER_MIN <= len(note) <= COUNTER_MAX:
        raise ValueError("condition")
    now = datetime.now(UTC)
    move_offer(offer, "accepted")
    offer.contacts_revealed_at = now
    offer.responded_at = now
    return note
