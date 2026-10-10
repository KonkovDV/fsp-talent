"""Internship track on an invitation. It does not change the match score or the grade.

Stages move one step forward, or close from any step.
"""
from __future__ import annotations

STAGES = ("sent", "screening", "trial", "hired", "closed")
_FORWARD = ("sent", "screening", "trial", "hired")


def next_stage(current: str | None, target: str) -> str:
    if target not in STAGES:
        raise ValueError("unknown")
    if target == "closed":
        return "closed"
    stage = current or "sent"
    if stage not in _FORWARD or target not in _FORWARD:
        raise ValueError("closed")
    if _FORWARD.index(target) != _FORWARD.index(stage) + 1:
        raise ValueError("skip")
    return target
