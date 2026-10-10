"""The API's client of the sandbox container: replies, refusals and an absent container."""
import json

import httpx
import pytest

from app.services.sandbox import SandboxUnavailable
from app.services.sandbox.remote import RemoteRunner


def _runner(handler) -> RemoteRunner:
    return RemoteRunner("/unused.sock", "tok", transport=httpx.MockTransport(handler))


def test_the_sandbox_client_reads_outputs_and_treats_failures_as_unavailable():
    seen = {}

    def ok(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.headers.get("X-Sandbox-Token")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"outputs": [4, True, 2 ** 70], "timed_out": False})

    result = _runner(ok).run("javascript", "function solve(xs) { return 4 }", [[[1]], [[2]], [[3]]])
    assert result.outputs == [4, None, None] and result.timed_out is False
    assert seen["token"] == "tok" and seen["body"]["language"] == "javascript"
    assert "expected" not in seen["body"]

    short = _runner(lambda r: httpx.Response(200, json={"outputs": [1], "timed_out": True}))
    assert short.run("python", "", [[[]], [[]]]).outputs == [None, None]

    for reply in (lambda r: httpx.Response(503, json={"error": "busy"}),
                  lambda r: httpx.Response(200, content=b"not json")):
        with pytest.raises(SandboxUnavailable):
            _runner(reply).run("python", "", [[[]]])

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no socket")

    with pytest.raises(SandboxUnavailable):
        _runner(down).run("python", "", [[[]]])
    with pytest.raises(SandboxUnavailable):
        _runner(down).languages()
    assert _runner(lambda r: httpx.Response(200, json={"ok": True, "languages": ["python", "javascript"]})
                   ).languages() == ("python", "javascript")


def test_a_required_sandbox_without_a_token_does_not_start(monkeypatch):
    from app.core.config import settings
    from app.services.sandbox import get_runner
    monkeypatch.setattr(settings, "SANDBOX_REQUIRED", True)
    monkeypatch.setattr(settings, "SANDBOX_TOKEN", "")
    monkeypatch.setattr(settings, "SANDBOX_SOCKET", "/run/sandbox/sandbox.sock")
    with pytest.raises(SandboxUnavailable):
        get_runner()
