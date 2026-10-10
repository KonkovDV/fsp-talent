"""Double-submit cookie for requests that authenticate with the refresh cookie.

The access token is a Bearer header, so a foreign page cannot attach it. The refresh token is an
HttpOnly cookie. A foreign page can ask the browser to send that cookie, but it cannot read a
second cookie and copy it into a header. API clients that send the refresh token in the body skip
this check.
"""
from __future__ import annotations

import hmac
import secrets

from fastapi import Response

from app.api.errors import ApiError
from app.core.config import settings

CSRF_COOKIE = "fsp_csrf"
CSRF_HEADER = "x-csrf-token"


def new_csrf() -> str:
    return secrets.token_urlsafe(32)


def attach_csrf(response: Response) -> None:
    response.set_cookie(
        key=CSRF_COOKIE,
        value=new_csrf(),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=False,
        samesite="lax",
    )


def clear_csrf(response: Response) -> None:
    response.delete_cookie(CSRF_COOKIE, path="/", secure=settings.COOKIE_SECURE, samesite="lax")


def check_csrf(cookie: str | None, header: str | None) -> None:
    left = cookie or ""
    right = header or ""
    if not left or not right or not hmac.compare_digest(left, right):
        raise ApiError(403, "csrf_invalid", "Запрос с cookie сессии без совпадающего токена")
