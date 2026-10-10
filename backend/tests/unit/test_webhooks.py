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
