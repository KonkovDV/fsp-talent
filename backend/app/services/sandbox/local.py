"""The child interpreter of the API image. Python only: there is no Node in that image."""
from __future__ import annotations

from typing import Any

from app.services.sandbox import RunResult, SandboxUnavailable


class LocalRunner:
    def languages(self) -> tuple[str, ...]:
        return ("python",)

    def run(self, language: str, source: str, cases: list[list[Any]]) -> RunResult:
        if language != "python":
            raise SandboxUnavailable("language_needs_sandbox")
        from app.services.code_lab import _run_cases

        outputs, timed_out = _run_cases(source, cases)
        return RunResult(outputs, timed_out)
