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


def card_fields(answers: dict | None, *, show_city: bool, show_fsp: bool, show_experience: bool,
                ) -> tuple[bool, bool, bool]:
    """What the anonymous card may add. A thin practice survey keeps specialization, grade and stack.

    City, years and the FSP lines stay off until three answers are yes, or until the survey is empty.
    The name and contacts are never in this decision: they open only after the candidate accepts.
    """
    if sees_senior(answers):
        return show_city, show_fsp, show_experience
    return False, False, False


def clean_answers(raw: dict) -> dict:
    return {key: bool(raw.get(key)) for key in KEYS}
