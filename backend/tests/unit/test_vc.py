import pytest

from app.core.config import settings
from app.services.vc import issuer


@pytest.fixture
def signing_key(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "VC_PRIVATE_KEY_PATH", str(tmp_path / "vc.pem"))
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://issuer.test")
    issuer._private_key.cache_clear()
    yield
    issuer._private_key.cache_clear()


def test_sign_verify_and_tamper(signing_key):
    credential = issuer.issue_achievement_credential("cred-1", "person-1", {
        "type": "FSPCompetitionResult", "eventId": "CR", "place": 1, "totalParticipants": 100,
    })
    assert credential["proof"]["cryptosuite"] == "eddsa-jcs-2022"
    assert credential["proof"]["proofValue"].startswith("z")
    assert len(credential["proof"]["proofValue"]) < 200
    assert issuer.verify_credential(credential)
    assert issuer.issuer_document()["verificationMethod"][0]["publicKeyMultibase"].startswith("z")

    tampered = {**credential, "credentialSubject": {"id": "urn:uuid:person-1", "achievement": {"place": 99}}}
    assert not issuer.verify_credential(tampered)
    forged = {**credential, "proof": {**credential["proof"], "proofValue": "z" + "1" * 20}}
    assert not issuer.verify_credential(forged)
