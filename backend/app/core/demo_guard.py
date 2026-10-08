"""Keep the published demo accounts usable for the jury.

The stand prints the password. A visitor must not be able to change it or erase the account.
The check is on only while DEMO_MODE is on, so a real deployment is not affected.
"""
from __future__ import annotations

from app.api.errors import ApiError
from app.core.config import settings

MESSAGE = "Демо-аккаунт: пароль и удаление закрыты, чтобы жюри могло войти"


def _suffixes() -> tuple[str, ...]:
    return tuple(part.strip().lower() for part in settings.DEMO_PROTECTED_SUFFIXES.split(",") if part.strip())


def is_protected(email: str | None) -> bool:
    """True only on the demo stand, and only for an address that ends with a configured suffix."""
    if not settings.DEMO_MODE or not email:
        return False
    lowered = email.strip().lower()
    return any(lowered.endswith(suffix) for suffix in _suffixes())


def reject_protected(email: str | None) -> None:
    """Stop a password change, a password reset, or an account deletion."""
    if is_protected(email):
        raise ApiError(409, "demo_protected", MESSAGE)
