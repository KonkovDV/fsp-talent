"""What happens after an assessment is stored. Listeners run after the commit.

The grade itself is written in the same transaction as the answers. A listener that fails
is logged and skipped: the finished test must not turn into an error for the candidate.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("app.profile_events")

_listeners: list = []


@dataclass(frozen=True)
class AssessmentFinished:
    participant_id: str
    trial: bool


def on_assessment_finished(fn):
    _listeners.append(fn)
    return fn


def forget_assessment_listener(fn) -> None:
    _listeners.remove(fn)


async def publish_assessment_finished(event: AssessmentFinished) -> None:
    for fn in tuple(_listeners):
        try:
            await fn(event)
        except Exception:
            logger.exception("listener after assessment failed")
