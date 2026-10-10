"""Company trust from facts the platform already has. Nothing here is typed in by the company as a level.

0 email is confirmed (every signed-in company).
1 the tax id passes the checksum. The registry of legal entities is not connected.
2 the email domain is the site domain.
3 an FSP partner, set only by `python -m app.services.trust partner`.
"""
from __future__ import annotations

from app.services.inn import inn_is_valid

INVITE_LIMIT = {0: 10, 1: 50, 2: 50, 3: 50}
VACANCY_LIMIT = {0: 1, 1: 3, 2: 10, 3: 30}
LABELS = {
    0: "почта подтверждена",
    1: "ИНН проверен по контрольной сумме, ЕГРЮЛ не подключён",
    2: "почта на домене сайта",
    3: "партнёр ФСП",
}
_NEXT = {
    0: "Укажите ИНН с верной контрольной суммой: лимит приглашений станет 50 в сутки.",
    1: "Укажите сайт на домене вашей почты.",
    2: "Уровень партнёра ФСП ставит администратор.",
    3: "",
}


def site_domain(website: str | None) -> str:
    host = (website or "").strip().lower()
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    host = host.split("/")[0].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def trust_level(employer) -> int:
    if getattr(employer, "fsp_partner", False):
        return 3
    email = (getattr(employer, "email", "") or "").strip().lower()
    domain = email.split("@", 1)[1] if "@" in email else ""
    if domain and domain == site_domain(getattr(employer, "website", None)):
        return 2
    if inn_is_valid(getattr(employer, "inn", None) or ""):
        return 1
    return 0


def invite_limit(level: int) -> int:
    return INVITE_LIMIT[level]


def vacancy_limit(level: int) -> int:
    return VACANCY_LIMIT[level]


def next_step(level: int) -> str:
    return _NEXT[level]
