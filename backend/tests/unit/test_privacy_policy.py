"""The privacy policy (152-FZ art. 18.1 part 2): published with the consents, read-only, and true to the code."""
import asyncio
import re

import pytest

from app.api.errors import ApiError
from app.legal import consent_documents, get_document, required_kinds
from app.services.identity import check_required_consents, give_consent


def _policy():
    doc = get_document("privacy_policy")
    assert doc is not None
    return doc


def test_policy_is_published_for_both_roles_but_is_not_a_consent():
    doc = _policy()
    assert set(doc.roles) == {"participant", "employer"}
    assert not doc.required and not doc.consent
    assert "privacy_policy" not in {d.kind for d in consent_documents()}
    assert "privacy_policy" not in required_kinds("participant") + required_kinds("employer")


def test_policy_cannot_be_accepted_or_sent_as_a_consent():
    with pytest.raises(ApiError) as err:
        check_required_consents("participant", ["terms", "pd_candidate", "privacy_policy"])
    assert err.value.code == "consent_unknown"
    with pytest.raises(ApiError) as err:
        asyncio.run(give_consent(None, "participant", None, "privacy_policy"))  # type: ignore[arg-type]
    assert err.value.code == "consent_unknown"


def test_policy_names_the_operator_without_invented_requisites():
    body = _policy().body_md
    assert "команда проекта «ФСП Талант», демонстрационный стенд" in body
    assert "лицензии MIT" in body
    assert "В промышленном контуре оператором выступает ФСП или владелец платформы" in body
    assert not re.search(r"\b\d{10}(\d{2})?\b", body), "ИНН/ОГРН не выдумываем"
    assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", body), "адрес почты оператора вписывает владелец"


@pytest.mark.parametrize("phrase", [
    "Какие данные собираем", "Зачем", "Кому передаём", "Сроки хранения", "Права субъекта",
    "Как отозвать согласие", "Несовершеннолетние", "за пределами Российской Федерации",
])
def test_policy_covers_every_required_section(phrase):
    assert phrase in _policy().body_md


def test_policy_matches_the_code_it_describes():
    body = _policy().body_md
    from app.services.guest import GUEST_TTL

    assert f"через {int(GUEST_TTL.total_seconds() // 3600)} часов" in body
    assert "30 дней" in body and "Argon2id" in body and "AES-256-GCM" in body
    assert "принял его приглашение" in body
    assert "с 15 лет" in body


def test_policy_has_no_superlatives():
    # 38-FZ art. 5 part 3: no «лучший», «самый», «единственный» without proof.
    assert not re.search(r"(?i)\b(лучш|самы|единствен|уникальн|№\s*1\b|гарантир)", _policy().body_md)
