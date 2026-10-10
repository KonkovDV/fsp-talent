"""Whether this company sees confirmed senior and lead cards.

No answers means the bank stays as it is. The count of yes answers is not returned to the company.
"""
from __future__ import annotations

KEYS = ("feedback", "platform_interview", "task_review", "salary_written")


def sees_senior(answers: dict | None) -> bool:
    if not isinstance(answers, dict):
        return True
    if not any(key in answers for key in KEYS):
        return True
    yes = sum(1 for key in KEYS if answers.get(key) is True)
    return yes >= 3


def clean_answers(raw: dict) -> dict:
    return {key: bool(raw.get(key)) for key in KEYS}
