import hashlib
import hmac
import json
import logging
import uuid
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization

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


def test_two_audiences_do_not_share_a_holder_id(signing_key):
    one = issuer.issue_audience_receipt(
        "cred-a", "participant-secret", "company-a",
        year=2024, status="всероссийское", bucket="топ-10%", discipline="Алгоритмическое",
    )
    other = issuer.issue_audience_receipt(
        "cred-b", "participant-secret", "company-b",
        year=2024, status="всероссийское", bucket="топ-10%", discipline="Алгоритмическое",
    )
    again = issuer.issue_audience_receipt(
        "cred-a", "participant-secret", "company-a",
        year=2024, status="всероссийское", bucket="топ-10%", discipline="Алгоритмическое",
    )
    stranger = issuer.issue_audience_receipt(
        "cred-c", "other-person", "company-a",
        year=2024, status="всероссийское", bucket="топ-10%", discipline="Алгоритмическое",
    )
    assert issuer.verify_credential(one) and issuer.verify_credential(other)
    left = one["credentialSubject"]["id"]
    right = other["credentialSubject"]["id"]
    assert left.startswith("urn:receipt:") and left != right
    assert left == again["credentialSubject"]["id"]
    assert left != stranger["credentialSubject"]["id"]
    blob = json.dumps(one) + json.dumps(other)
    assert "participant-secret" not in blob and "other-person" not in blob
    public = issuer._private_key().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    forged = hmac.new(
        public, b"receipt\nparticipant-secret\ncompany-a", hashlib.sha256).hexdigest()
    assert forged != left.removeprefix("urn:receipt:")


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


def test_a_public_credential_copy_drops_the_subject_id():
    from app.api.v1.public import _without_subject_id

    shown = _without_subject_id({
        "id": "urn:uuid:credential",
        "credentialSubject": {"id": "urn:uuid:person", "achievement": {"name": "Победа"}},
    })
    assert shown["id"] == "urn:uuid:credential"
    assert "id" not in shown["credentialSubject"]
    assert shown["credentialSubject"]["achievement"]["name"] == "Победа"


def test_sd_jwt_carries_the_stored_credential_id_outside_the_disclosed_claims(signing_key):
    token, disclosures = issuer.issue_sd_jwt("person-1", {"skill": "Python"}, jti="cred-1")
    shown = issuer.present_sd_jwt(token, disclosures, {"skill"})
    assert issuer.sd_jwt_jti(shown) == "cred-1"
    assert issuer.verify_sd_jwt(shown) == {"skill": "Python"}
    assert "person-1" not in shown
    token, disclosures = issuer.issue_sd_jwt("person-1", {"skill": "Python"})
    shown = issuer.present_sd_jwt(token, disclosures, {"skill"})
    payload = json.loads(issuer._b64url_decode(shown.split("~", 1)[0].split(".")[1]))
    assert "person-1" not in shown and payload["sub"] != "urn:uuid:person-1"
    assert issuer.verify_sd_jwt(shown) == {"skill": "Python"}


def test_an_expired_sd_jwt_is_refused(signing_key):
    token, disclosures = issuer.issue_sd_jwt("person-1", {"skill": "Python"})
    header_b64, payload_b64, _signature = token.split(".")
    payload = json.loads(issuer._b64url_decode(payload_b64))
    payload["iat"] = 1
    payload["exp"] = 2
    header = json.loads(issuer._b64url_decode(header_b64))
    signing = f"{issuer._b64url(issuer._jcs(header))}.{issuer._b64url(issuer._jcs(payload))}".encode()
    signed = signing.decode() + "." + issuer._b64url(issuer._private_key().sign(signing))
    shown = issuer.present_sd_jwt(signed, disclosures, {"skill"})
    assert issuer.verify_sd_jwt(shown) is None


def test_a_revoked_sd_jwt_keeps_its_signature_and_loses_validity(signing_key):
    credential_id = str(uuid.uuid4())
    token, disclosures = issuer.issue_sd_jwt("person-1", {"skill": "Python"}, jti=credential_id)
    shown = issuer.present_sd_jwt(token, disclosures, {"skill"})
    assert issuer.sd_jwt_status(shown, revoked=False) == {
        "valid": True, "signature": True, "revoked": False,
    }
    assert issuer.sd_jwt_status(shown, revoked=True) == {
        "valid": False, "signature": True, "revoked": True,
    }
    assert issuer.sd_jwt_status(shown + "tamper", revoked=True)["signature"] is False
    assert issuer.sd_jwt_status(shown + "tamper", revoked=True)["revoked"] is False


@pytest.mark.asyncio
async def test_public_sd_jwt_check_reads_the_revocation_row(signing_key):
    from app.api.v1.public import SdJwtBody, verify_posted_sd_jwt

    credential_id = uuid.uuid4()
    token, disclosures = issuer.issue_sd_jwt("person-1", {"skill": "Python"}, jti=str(credential_id))
    shown = issuer.present_sd_jwt(token, disclosures, {"skill"})

    class Db:
        def __init__(self, row):
            self.row = row

        async def get(self, model, ident=None, **kwargs):
            return self.row if ident == credential_id else None

    fresh = await verify_posted_sd_jwt(SdJwtBody(sd_jwt=shown), Db(SimpleNamespace(revoked_at=None)))
    assert fresh == {"valid": True, "signature": True, "revoked": False}
    stopped = await verify_posted_sd_jwt(SdJwtBody(sd_jwt=shown), Db(SimpleNamespace(revoked_at=object())))
    assert stopped == {"valid": False, "signature": True, "revoked": True}
    unknown = await verify_posted_sd_jwt(SdJwtBody(sd_jwt=shown), Db(None))
    assert unknown == {"valid": True, "signature": True, "revoked": False}
