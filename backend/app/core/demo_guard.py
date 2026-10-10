"""Keep the published demo accounts usable for the jury.

The stand prints the password. A visitor must not be able to change it or erase the account.
The check is on only while DEMO_MODE is on, so a real deployment is not affected.
"""
from __future__ import annotations

from app.api.errors import ApiError
from app.core.config import settings

MESSAGE = "Демо-аккаунт: пароль и удаление закрыты, чтобы жюри могло войти"
# Printed logins only. A lookalike such as ivan@x.demo is an ordinary account.
PUBLISHED_EMAILS = frozenset({
    "fsp001@demo.talent", "fsp002@demo.talent", "nofsp@demo.talent",
    "hr@sibcode.demo", "hr@quantumlab.demo", "hr@perimeter.demo",
    "hr@cloudwhale.demo", "hr@robotech.demo",
    *(f"jury{n}@demo.talent" for n in range(1, 11)),
})


def is_protected(email: str | None) -> bool:
    """True only on the demo stand, and only for an address the seed publishes."""
    if not settings.DEMO_MODE or not email:
        return False
    return email.strip().lower() in PUBLISHED_EMAILS


def reject_reserved(email: str | None) -> None:
    """The published addresses are not open for a new registration."""
    if is_protected(email):
        raise ApiError(422, "reserved_email", "Этот адрес зарезервирован для демо-стенда")


def reject_protected(email: str | None) -> None:
    """Stop a password change, a password reset, or an account deletion."""
    if is_protected(email):
        raise ApiError(409, "demo_protected", MESSAGE)
