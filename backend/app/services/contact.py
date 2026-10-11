"""Allowed contact for an invitation (audit-3 P2-1): an e-mail, a Telegram @handle or an E.164 phone.

A blacklist of «http»/«www» let through t.me/x, evil.ru/login and bit.ly/…; a whitelist does not.
Several contacts may be listed, separated by a comma or a semicolon.
"""
from __future__ import annotations

import re

EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
TELEGRAM = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
PHONE = re.compile(r"^\+[1-9]\d{6,14}$")   # E.164
_PHONE_SEPARATORS = re.compile(r"[\s\-()]")


def contact_ok(value: str) -> bool:
    parts = [p.strip() for p in re.split(r"[;,]", value or "")]
    if not parts or any(not p for p in parts) or len(parts) > 3:
        return False
    for part in parts:
        if EMAIL.match(part) or TELEGRAM.match(part):
            continue
        if PHONE.match(_PHONE_SEPARATORS.sub("", part)):
            continue
        return False
    return True
