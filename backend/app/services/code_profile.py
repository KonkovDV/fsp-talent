"""A public code login the candidate types. It is a contact, not a score and not a grade."""
from __future__ import annotations

import re

_LOGIN = re.compile(r"[A-Za-z0-9-]{1,39}")


def clean_github(raw: str | None) -> str | None:
    text = (raw or "").strip().lstrip("@")
    if not text:
        return None
    if _LOGIN.fullmatch(text) is None:
        raise ValueError("Логин: латиница, цифры и дефис, до 39 знаков")
    return text


def code_profile_line(login: str | None) -> str | None:
    if not (login or "").strip():
        return None
    return "Указан публичный код. Логин откроется после согласия."
