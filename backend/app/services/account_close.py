"""Closing an account. The typed word stops a stray click. A password, when the account has one, is required too."""
from __future__ import annotations


def close_allowed(word: str, has_password: bool, password_ok: bool) -> str | None:
    if word.strip().casefold() != "удалить":
        return "word"
    if has_password and not password_ok:
        return "password"
    return None
