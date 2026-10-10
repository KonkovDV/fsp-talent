from app.services.vc.did_web import did_document, did_web_id


def test_the_did_is_the_host_and_carries_the_key():
    assert did_web_id("https://talent.example/api") == "did:web:talent.example"
    assert did_web_id("http://127.0.0.1:8000") == "did:web:127.0.0.1%3A8000"
    doc = did_document("https://talent.example", "z6Mkexample")
    assert doc["id"] == "did:web:talent.example"
    assert doc["verificationMethod"][0]["publicKeyMultibase"] == "z6Mkexample"
    assert doc["assertionMethod"] == ["did:web:talent.example#key-1"]
