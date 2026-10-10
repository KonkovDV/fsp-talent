"""The sandbox container, reached over a Unix socket on a shared volume. It has no network of its own."""
from __future__ import annotations

from typing import Any

import httpx

from app.services.sandbox import RunResult, SandboxUnavailable

MAX_BITS = 60
TIMEOUT_S = 10.0


class RemoteRunner:
    def __init__(self, socket_path: str, token: str = "", transport: httpx.BaseTransport | None = None):
        self._transport = transport or httpx.HTTPTransport(uds=socket_path)
        self._headers = {"X-Sandbox-Token": token} if token else {}

    def _client(self) -> httpx.Client:
        return httpx.Client(transport=self._transport, base_url="http://sandbox", timeout=TIMEOUT_S,
                            headers=self._headers)

    def languages(self) -> tuple[str, ...]:
        try:
            with self._client() as client:
                body = client.get("/health").json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SandboxUnavailable("sandbox_down") from exc
        return tuple(lang for lang in body.get("languages", []) if isinstance(lang, str))

    def run(self, language: str, source: str, cases: list[list[Any]]) -> RunResult:
        try:
            with self._client() as client:
                resp = client.post("/run", json={"language": language, "source": source, "cases": cases})
        except httpx.HTTPError as exc:
            raise SandboxUnavailable("sandbox_down") from exc
        if resp.status_code != 200:
            raise SandboxUnavailable(f"sandbox_{resp.status_code}")
        try:
            body = resp.json()
        except ValueError as exc:
            raise SandboxUnavailable("sandbox_reply") from exc
        raw = body.get("outputs") if isinstance(body, dict) else None
        if not isinstance(raw, list) or len(raw) != len(cases):
            return RunResult([None] * len(cases), False)
        outputs = [v if isinstance(v, int) and not isinstance(v, bool) and v.bit_length() <= MAX_BITS else None
                   for v in raw]
        return RunResult(outputs, bool(body.get("timed_out")))
