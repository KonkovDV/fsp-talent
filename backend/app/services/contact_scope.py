"""Which contacts a candidate opens to one company.

The candidate picks channels when accepting an invitation or when answering "yes, if". The company sees
only those channels: in its cabinet, in webhooks, in the ATS export and in vacancy applications. The name
stays visible after acceptance, the company needs to know whom it writes to. A row without a stored list
predates this choice and opens every channel, as it did when the candidate accepted.
"""
from __future__ import annotations

from collections.abc import Iterable

CHANNELS: tuple[str, ...] = ("email", "telegram", "phone", "github")
LABELS = {"email": "email", "telegram": "Telegram", "phone": "телефон", "github": "GitHub"}


class EmptyScope(ValueError):
    """None of the picked channels is filled in the profile."""


def available(person) -> list[str]:
    """Channels the person has filled in, in a fixed order."""
    return [ch for ch in CHANNELS if str(getattr(person, ch, None) or "").strip()]


def clean_share(share: Iterable[str], person) -> list[str]:
    picked = set(share)
    channels = [ch for ch in available(person) if ch in picked]
    if not channels:
        raise EmptyScope("scope")
    return channels


def scope(offer) -> list[str]:
    stored = getattr(offer, "shared_contacts", None)
    if stored is None:
        return list(CHANNELS)
    return [ch for ch in CHANNELS if ch in stored]


def contacts(person, channels: Iterable[str]) -> dict[str, str | None]:
    """Every channel key is present; a channel the candidate did not open is None."""
    allowed = set(channels)
    return {ch: (getattr(person, ch, None) if ch in allowed else None) for ch in CHANNELS}


def describe(channels: Iterable[str]) -> str:
    chosen = set(channels)
    return ", ".join(LABELS[ch] for ch in CHANNELS if ch in chosen)
