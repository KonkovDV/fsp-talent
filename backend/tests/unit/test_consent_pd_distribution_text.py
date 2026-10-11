"""AUD F-12: the distribution consent says what a lookup by FSP ID shows, and that withdrawal turns it off."""
from app.legal import get_document


def test_distribution_consent_names_the_fsp_id_lookup_and_its_limits():
    doc = get_document("pd_distribution")
    text = doc.body_md
    assert doc.version == "1.1"
    assert text.count("ФСП ID") >= 2
    assert "/api/v1/public/telegram/achievements?fsp_id=" in text
    assert "Сам ФСП ID не показывается" in text
    assert "нет имени, контактов и грейда" in text
    assert "поиск протоколов по ФСП ID" in text  # withdrawal turns the lookup off


def test_distribution_consent_stays_separate_and_optional():
    doc = get_document("pd_distribution")
    assert not doc.required
    assert "ст. 10.1" in doc.body_md
