import logging
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.vc import issuer


@pytest.fixture
def signing_key(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "VC_PRIVATE_KEY_PATH", str(tmp_path / "vc.pem"))
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://issuer.test")
    issuer._private_key.cache_clear()
    issuer.public_key_multibase.cache_clear()
    issuer._public_key_obj.cache_clear()
    yield
    issuer._private_key.cache_clear()
    issuer.public_key_multibase.cache_clear()
    issuer._public_key_obj.cache_clear()


def test_sign_verify_and_tamper(signing_key):
    credential = issuer.issue_achievement_credential("cred-1", "person-1", {
        "type": "FSPCompetitionResult", "eventId": "CR", "place": 1, "totalParticipants": 100,
    })
    assert credential["proof"]["cryptosuite"] == "eddsa-jcs-2022"
    assert "OpenBadgeCredential" in credential["type"]
    assert credential["credentialStatus"]["type"] == "FSPCredentialStatus"
    assert credential["credentialStatus"]["id"].endswith("/cred-1/status")
    assert credential["proof"]["proofValue"].startswith("z")
    assert len(credential["proof"]["proofValue"]) < 200
    assert issuer.verify_credential(credential)
    assert issuer.issuer_document()["verificationMethod"][0]["publicKeyMultibase"].startswith("z")

    tampered = {**credential, "credentialSubject": {"id": "urn:uuid:person-1", "achievement": {"place": 99}}}
    assert not issuer.verify_credential(tampered)
    forged = {**credential, "proof": {**credential["proof"], "proofValue": "z" + "1" * 20}}
    assert not issuer.verify_credential(forged)


def test_derived_credential_omits_the_event_title(signing_key):
    credential = issuer.issue_derived_credential(
        "cred-2", "person-1", year=2024, status="всероссийское", bucket="топ-10%", discipline="Алгоритмическое",
    )
    text = str(credential)
    assert issuer.verify_credential(credential)
    assert "credentialStatus" not in credential
    assert "DerivedFSPClaim" in credential["credentialSubject"]["achievement"]["type"]
    assert "eventName" not in text and "2024" in text and "топ-10%" in text


def test_credential_uuid_reads_only_a_real_uuid():
    from app.api.v1.public import credential_uuid
    raw = "6f9b1c2e-3a44-4d1e-9c0a-1b2c3d4e5f60"
    assert credential_uuid({"id": f"urn:uuid:{raw}"}) is not None
    assert str(credential_uuid({"id": f"urn:uuid:{raw}"})) == raw
    assert credential_uuid({"id": "urn:uuid:cred-1"}) is None
    assert credential_uuid({"id": 12}) is None
    assert credential_uuid({}) is None


def test_a_root_process_gives_the_new_key_to_appuser(signing_key, monkeypatch):
    given = {}
    account = SimpleNamespace(pw_uid=4242, pw_gid=4243)

    def getpwnam(name):
        if name != "appuser":
            raise KeyError(name)
        return account

    monkeypatch.setattr(issuer.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(issuer.os, "chown", lambda path, uid, gid: given.update(path=path, uid=uid, gid=gid),
                        raising=False)
    monkeypatch.setitem(__import__("sys").modules, "pwd", SimpleNamespace(getpwnam=getpwnam))
    issuer._private_key()
    assert given["uid"] == 4242 and given["gid"] == 4243
    assert given["path"].endswith("vc.pem")


def test_a_process_that_is_not_root_leaves_the_key_alone(signing_key, monkeypatch):
    called = []
    monkeypatch.setattr(issuer.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(issuer.os, "chown", lambda *args: called.append(args), raising=False)
    issuer._private_key()
    assert called == []


def test_an_unreadable_key_is_named_in_the_log(signing_key, monkeypatch, caplog):
    path = settings.VC_PRIVATE_KEY_PATH
    with open(path, "wb") as handle:
        handle.write(b"present")
    real_open = open

    def refuse(target, mode="r", *args, **kwargs):
        if str(target) == path and "b" in str(mode):
            raise PermissionError(13, "Permission denied", target)
        return real_open(target, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", refuse)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(PermissionError):
            issuer._private_key()
    assert path in caplog.text and "appuser" in caplog.text


def test_sd_jwt_hides_the_event_title_until_it_is_disclosed(signing_key):
    token, disclosures = issuer.issue_sd_jwt("person-1", {
        "year": 2024, "bucket": "топ-10%", "eventName": "Чемпионат России",
    })
    shown = issuer.present_sd_jwt(token, disclosures, {"year", "bucket"})
    claims = issuer.verify_sd_jwt(shown)
    assert claims == {"year": 2024, "bucket": "топ-10%"}
    assert "Чемпионат России" not in shown
    opened = issuer.present_sd_jwt(token, disclosures, {"year", "bucket", "eventName"})
    assert issuer.verify_sd_jwt(opened)["eventName"] == "Чемпионат России"
    assert issuer.verify_sd_jwt(shown + "tamper") is None
