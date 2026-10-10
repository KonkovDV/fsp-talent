"""Where a practice solution runs: a local child process or the sandbox container.

The runner receives the source and the inputs and returns the outputs. Expected values stay
with the caller, so neither runner can leak them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RunResult:
    outputs: list[int | None]
    timed_out: bool = False


class SandboxUnavailable(RuntimeError):
    """No runner can take this language now. The API answers 503 and stores nothing."""


class Runner(Protocol):
    def languages(self) -> tuple[str, ...]: ...

    def run(self, language: str, source: str, cases: list[list[Any]]) -> RunResult: ...


def get_runner() -> Runner:
    from app.core.config import settings

    if settings.SANDBOX_SOCKET:
        from app.services.sandbox.remote import RemoteRunner
        return RemoteRunner(settings.SANDBOX_SOCKET, settings.SANDBOX_TOKEN)
    if settings.SANDBOX_REQUIRED:
        raise SandboxUnavailable("sandbox_not_configured")
    from app.services.sandbox.local import LocalRunner
    return LocalRunner()
