"""Row-level scope for one request or one worker job.

The database policies read these settings. An empty scope hides private rows. Auth, public
pages, the seed and the worker set a bypass; a signed-in request sets the account id.
"""
from __future__ import annotations

from contextvars import ContextVar, Token

_scope: ContextVar[dict] = ContextVar("rls_scope", default={})


def current() -> dict:
    return _scope.get()


def set_rls(*, bypass: bool = False, participant_id: str = "", employer_id: str = "") -> Token:
    return _scope.set({
        "bypass": bypass,
        "participant_id": participant_id,
        "employer_id": employer_id,
    })


def reset_rls(token: Token) -> None:
    _scope.reset(token)


def bypass_rls() -> Token:
    return set_rls(bypass=True)
