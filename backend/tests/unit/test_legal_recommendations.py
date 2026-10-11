"""149-FZ art. 10.2-2 and RKN order No. 149 of 06.10.2023: notice + rules published, read-only, true to the code."""
from app.legal import consent_documents, get_document, required_kinds


def test_rules_are_published_read_only_for_both_roles():
    doc = get_document("recommendations")
    assert doc is not None and not doc.required and not doc.consent
    assert set(doc.roles) == {"participant", "employer"}
    assert "recommendations" not in {d.kind for d in consent_documents()}
    assert "recommendations" not in required_kinds("participant") + required_kinds("employer")


def test_rules_carry_the_mandatory_notice_and_sources():
    body = get_document("recommendations").body_md
    assert "На информационном ресурсе применяются рекомендательные технологии" in body
    for phrase in ("Какие сведения используются и откуда", "Как работает", "Контакты владельца ресурса"):
        assert phrase in body


def test_policy_points_to_the_rules_and_states_response_deadline():
    body = get_document("privacy_policy").body_md
    assert "10.2-2" in body and "10 рабочих дней" in body and "журналы веб-сервера" in body


def test_city_claim_matches_matching_code():
    from app.services.matching import conditions_value
    assert "A mismatch is not a ban" in conditions_value.__doc__
    assert "кандидат из выдачи не исключается" in get_document("recommendations").body_md
