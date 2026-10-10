import socket

import pytest

from app.services.page_draft import PageDraftError, page_text, public_host


def test_tags_and_scripts_drop_out_of_the_draft_text():
    html = "<html><script>secret()</script><body><p>Ищем Python в Москве</p></body></html>"
    assert page_text(html) == "Ищем Python в Москве"
    assert "secret" not in page_text(html)


def test_a_loopback_host_is_refused():
    with pytest.raises(PageDraftError):
        public_host("127.0.0.1")
    with pytest.raises(PageDraftError):
        public_host("10.1.1.1")


def test_an_unclosed_script_does_not_stay_in_the_draft():
    html = "<p>Ищем Python</p><script>secret()"
    assert "secret" not in page_text(html)
    assert "Ищем Python" in page_text(html)


def test_a_name_with_one_private_address_is_refused(monkeypatch):
    def fake(*_args, **_kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.0.1", 0)),
        ]

    monkeypatch.setattr("app.services.page_draft.socket.getaddrinfo", fake)
    with pytest.raises(PageDraftError):
        public_host("example.test")
