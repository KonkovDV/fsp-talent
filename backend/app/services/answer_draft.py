"""An unsent answer on the current item. Scoring ignores it until the candidate submits."""
from __future__ import annotations


class DraftStale(Exception):
    """The tab holds an older version than the one already stored."""


class DraftBoth(Exception):
    """A choice and a typed number arrived together."""


def apply_draft(version: int, presented: int, index: int | None, text: str | None,
                ) -> tuple[int, int | None, str | None]:
    if presented != version:
        raise DraftStale
    cleaned = (text or "").strip()[:32] or None
    if index is not None and cleaned is not None:
        raise DraftBoth
    return version + 1, index, cleaned
