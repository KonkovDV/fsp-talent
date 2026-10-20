from datetime import UTC, datetime, timedelta

import pytest

from app.services.webhooks import check_url, classify, sign_headers, signature_ok

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def test_signature_accepts_the_same_body_and_rejects_a_late_one():
    body = b'{"type":"offer.accepted"}'
    headers = sign_headers("whsec_test", "id-1", body, NOW)
    assert signature_ok("whsec_test", headers, body, NOW)
    assert not signature_ok("whsec_test", headers, body + b" ", NOW)
    assert not signature_ok("whsec_test", headers, body, NOW + timedelta(minutes=10))


def test_retries_then_stop_and_410_stops_at_once():
    assert classify(204, 0) == ("delivered", None)
    assert classify(500, 0) == ("pending", 60)
    assert classify(500, 4) == ("pending", 43200)
    assert classify(500, 5) == ("dead", None)
    assert classify(410, 0) == ("dead", None)


def test_plain_http_to_another_host_is_rejected():
    with pytest.raises(ValueError):
        check_url("http://example.com/hook")


def test_the_stand_sandbox_is_allowed(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://localhost")
    assert check_url("http://localhost/api/v1/integrations/sandbox/abc").endswith("/abc")


@pytest.mark.parametrize("url", [
    # SEC3-02: another port of the stand host
    "http://localhost:8000/api/v1/integrations/sandbox/abc",
    "http://localhost:6379/api/v1/integrations/sandbox/abc",
    # SEC3-02: «..» after the sandbox prefix, plain and percent-encoded (httpx collapses it to /metrics)
    "http://localhost/api/v1/integrations/sandbox/../../../../metrics",
    "http://localhost/api/v1/integrations/sandbox/%2e%2e/%2e%2e/admin",
    "http://localhost/api/v1/integrations/sandbox/%252e%252e/x",
    "http://localhost/api/v1/integrations/sandbox/./x",
    "http://localhost/api/v1/integrations/sandbox\\..\\x",
    # any other path of the stand
    "http://localhost/api/v1/employer/integrations",
])
def test_the_stand_host_only_takes_the_sandbox_receiver(monkeypatch, url):
    from app.core.config import settings
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://localhost")
    with pytest.raises(ValueError):
        check_url(url)


def test_the_sandbox_on_the_default_port_written_out_is_allowed(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://stand.example")
    assert check_url("https://stand.example:443/api/v1/integrations/sandbox/abc").endswith("/abc")


async def test_delivery_connects_to_the_checked_address(monkeypatch):
    """SEC3-03: the name is resolved once; the request goes to that IP, not to a second (rebound) answer."""
    import httpx

    from app.services import page_draft, webhooks

    answers = iter(["93.184.216.34", "127.0.0.1"])
    monkeypatch.setattr(page_draft, "public_ip", lambda host: next(answers))
    seen = {}

    async def fake_send(self, request):
        seen["host"] = request.url.host
        seen["header"] = request.headers.get("host")
        seen["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(204, request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_send)
    code, _ = await webhooks.post_delivery("https://ats.example/hook", "whsec_x", "d-1", "{}")
    assert code == 204
    assert seen == {"host": "93.184.216.34", "header": "ats.example", "sni": "ats.example"}


async def test_delivery_to_a_private_answer_is_refused(monkeypatch):
    from app.services import page_draft, webhooks

    def private(host):
        raise page_draft.PageDraftError("Адрес страницы не публичный")

    monkeypatch.setattr(page_draft, "public_ip", private)
    with pytest.raises(ValueError):
        await webhooks.post_delivery("https://rebind.example/hook", "whsec_x", "d-1", "{}")


class Scoped:
    """A session under row-level security: the company's endpoints are visible only with the bypass on."""

    def __init__(self, endpoints, fail=False):
        import uuid as _uuid
        self.endpoints = endpoints
        self.fail = fail
        self.bypass = ""
        self.added = []
        self.trace = []
        self._uuid = _uuid

    async def flush(self):
        self.trace.append(("flush", self.bypass, len(self.added)))

    async def scalar(self, stmt):
        return self.bypass

    async def execute(self, stmt):
        if "set_config('app.bypass_rls'" in str(stmt):
            self.bypass = stmt.compile().params.get("value", "")
        self.trace.append(("set", self.bypass))

    async def scalars(self, stmt):
        self.trace.append(("select", self.bypass))
        if self.fail:
            raise RuntimeError("database went away")
        return list(self.endpoints) if self.bypass == "on" else []

    def add(self, obj):
        self.added.append(obj)


async def test_a_candidate_request_still_queues_the_company_event():
    import uuid
    from types import SimpleNamespace

    from app.services.webhooks import enqueue

    db = Scoped([SimpleNamespace(id=uuid.uuid4())])
    queued = await enqueue(db, uuid.uuid4(), "contacts.revoked", {"candidate": {"ref": "c_1", "delete": True}})
    assert queued == 1 and len(db.added) == 1
    assert db.trace[0] == ("flush", "", 0), "the request's own changes are written under its own scope"
    assert ("select", "on") in db.trace
    assert ("flush", "on", 1) in db.trace, "the delivery is written while the bypass is on"
    assert db.bypass == "", "the request scope is back after the event"


async def test_the_scope_is_restored_when_the_lookup_fails():
    import uuid

    from app.services.webhooks import enqueue

    db = Scoped([], fail=True)
    with pytest.raises(RuntimeError):
        await enqueue(db, uuid.uuid4(), "offer.accepted", {})
    assert db.bypass == "" and db.added == []
