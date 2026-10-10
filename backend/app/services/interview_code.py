"""Drafts of a coding step after an accepted invitation.

A dispute is a note. It does not change the grade and it does not call a model.
"""
from __future__ import annotations

SNAPSHOTS = 8


class CodeStale(Exception):
    """The editor holds an older draft than the one already stored."""


def apply_code_draft(version: int, presented: int, text: str, snapshots: list | None) -> tuple[int, str, list]:
    if presented != version:
        raise CodeStale
    cleaned = (text or "").strip()[:8000]
    nxt = version + 1
    shots = [dict(item) for item in (snapshots or [])]
    shots.append({"version": nxt, "text": cleaned})
    return nxt, cleaned, shots[-SNAPSHOTS:]


def code_view(problem: dict | None, prompt: str, draft: str, version: int,
              snapshots: list, dispute: str | None) -> dict:
    """What both sides see. There is no score and no grade in this object."""
    return {
        "problem": problem,
        "prompt": prompt,
        "draft": draft,
        "version": version,
        "snapshots": snapshots,
        "dispute": dispute,
    }
