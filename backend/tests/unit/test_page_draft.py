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
