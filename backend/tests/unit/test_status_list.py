"""W3C Bitstring Status List v1.0: random positions, one signed public list, a set bit means revoked."""
import json
import uuid

import pytest

from app.api.v1 import public
from app.core.config import settings
from app.services.vc import issuer, status_list
from app.services.vc.status_list import LIST_SIZE, decode, encode, is_set, list_credential, status_entry


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


def test_the_first_position_is_the_left_most_bit_and_the_list_has_the_minimum_length():
    raw = decode(encode([0, 9, LIST_SIZE - 1]))
    assert len(raw) == LIST_SIZE // 8
    assert raw[0] == 0x80 and raw[1] == 0x40 and raw[-1] == 0x01
    assert is_set(raw, 0) and is_set(raw, 9) and is_set(raw, LIST_SIZE - 1)
    assert not is_set(raw, 1)


def test_the_encoding_is_multibase_base64url_without_padding():
    encoded = encode([])
    assert encoded.startswith("u") and "=" not in encoded and "+" not in encoded and "/" not in encoded
    assert encode([5]) == encode([5])
    with pytest.raises(ValueError):
        decode("z" + encoded[1:])
    with pytest.raises(ValueError):
        status_entry(LIST_SIZE)


def test_the_list_is_a_signed_credential_of_the_right_type(signing_key):
    doc = list_credential([3, 42])
    assert doc["type"] == ["VerifiableCredential", "BitstringStatusListCredential"]
    subject = doc["credentialSubject"]
    assert subject["type"] == "BitstringStatusList" and subject["statusPurpose"] == "revocation"
    assert doc["id"] == "http://issuer.test/api/v1/public/status-lists/1"
    assert issuer.verify_credential(doc)
    raw = decode(subject["encodedList"])
    assert is_set(raw, 3) and is_set(raw, 42) and not is_set(raw, 4)
    tampered = json.loads(json.dumps(doc))
    tampered["credentialSubject"]["encodedList"] = encode([])
    assert not issuer.verify_credential(tampered)


def test_a_credential_with_an_index_carries_both_status_entries(signing_key):
    cred = issuer.issue_achievement_credential("c-1", "p-1", {"type": "FSPCompetitionResult"}, status_index=77)
    own, bitstring = cred["credentialStatus"]
    assert own["type"] == "FSPCredentialStatus"
    assert bitstring == {
        "id": "http://issuer.test/api/v1/public/status-lists/1#77", "type": "BitstringStatusListEntry",
        "statusPurpose": "revocation", "statusListIndex": "77",
        "statusListCredential": "http://issuer.test/api/v1/public/status-lists/1",
    }
    assert issuer.verify_credential(cred)
    plain = issuer.issue_achievement_credential("c-2", "p-1", {"type": "FSPCompetitionResult"})
    assert plain["credentialStatus"]["type"] == "FSPCredentialStatus"


def test_a_receipt_carries_only_the_list_entry(signing_key):
    receipt = issuer.issue_audience_receipt("r-1", "p-1", "r-1", year=2024, status="всероссийское",
                                            bucket="топ-10%", discipline="Алгоритмическое", status_index=5)
    entry = receipt["credentialStatus"]
    assert entry["type"] == "BitstringStatusListEntry" and entry["statusListIndex"] == "5"
    assert "/public/credentials/" not in json.dumps(entry)
    assert issuer.verify_credential(receipt)


async def test_the_receipt_row_keeps_its_list_position(signing_key, monkeypatch):
    from datetime import date
    from types import SimpleNamespace

    from app.api.v1 import candidates

    pid = uuid.uuid4()
    result = SimpleNamespace(id=uuid.uuid4(), participant_id=pid, event_date=date(2024, 5, 1),
                             competition_status="all_russian", place=3, total_participants=100,
                             discipline="algo", event_name="Кубок")

    async def calm(*args, **kwargs):
        return False

    class Store:
        def __init__(self):
            self.added = []

        async def get(self, model, ident, **kwargs):
            return result

        async def scalar(self, stmt):
            return None

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            pass

    monkeypatch.setattr(candidates, "too_many", calm)
    monkeypatch.setattr(status_list.secrets, "randbelow", lambda n: 314)
    db = Store()
    out = await candidates.present_result(result.id, {"sub": str(pid)}, db)
    [row] = [o for o in db.added if type(o).__name__ == "VerifiableCredential"]
    assert row.status_index == 314
    assert out["credential"]["credentialStatus"]["statusListIndex"] == "314"


class Ingest:
    """Assigns ids on flush like the database does and knows which status positions are taken."""

    def __init__(self, known_events=()):
        self.added = []
        self.known_events = list(known_events)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def scalar(self, stmt):
        index = stmt.compile().params.get("status_index_1")
        return next((o.id for o in self.added
                     if type(o).__name__ == "VerifiableCredential" and o.status_index == index), None)

    async def scalars(self, stmt):
        return list(self.known_events)


def _protocol():
    from datetime import date

    from app.services.fsp.mock import FSPParticipant, FSPResult
    rows = [FSPResult(f"EV{i}", f"Событие {i}", "algorithmic", "russia_cup", i + 1, 100, False, 1,
                      date(2025, 3, i + 1)) for i in range(3)]
    return FSPParticipant("FSP-T1", "Тест", "Москва", date(1999, 1, 1), results=rows)


async def test_fsp_results_each_get_their_own_list_position(signing_key, monkeypatch):
    from app.services import profile

    picks = iter([7, 7, 11, 13])
    monkeypatch.setattr(status_list.secrets, "randbelow", lambda n: next(picks))
    db = Ingest()
    person = await profile.ingest_from_fsp(db, _protocol())
    creds = [o for o in db.added if type(o).__name__ == "VerifiableCredential"]
    assert sorted(c.status_index for c in creds) == [7, 11, 13]
    for cred in creds:
        entries = cred.credential_json["credentialStatus"]
        assert entries[1]["statusListIndex"] == str(cred.status_index)
        assert cred.participant_id == person.id and issuer.verify_credential(cred.credential_json)
    assert person.fsp_id == "FSP-T1" and person.is_minor is False


async def test_a_repeat_protocol_adds_only_new_lines(signing_key):
    from types import SimpleNamespace

    from app.services import profile

    person = SimpleNamespace(id=uuid.uuid4(), fsp_id=None, display_name="Своё имя", region=None,
                             birth_date=None, is_minor=False, fsp_linked_at=None)
    data = _protocol()
    db = Ingest(known_events=["EV0", "EV1"])
    assert await profile.append_new_results(db, person, data) == 1
    assert [o.event_id for o in db.added if type(o).__name__ == "Result"] == ["EV2"]
    assert len(data.results) == 3 and person.display_name == "Своё имя"
    assert await profile.append_new_results(Ingest(known_events=["EV0", "EV1", "EV2"]), person, data) == 0


class Taken:
    def __init__(self, used):
        self.used = set(used)
        self.asked = 0

    async def scalar(self, stmt):
        self.asked += 1
        index = stmt.compile().params.get("status_index_1")
        return uuid.uuid4() if index in self.used else None


async def test_a_new_index_skips_taken_positions(monkeypatch):
    picks = iter([5, 5, 9, 11])
    monkeypatch.setattr(status_list.secrets, "randbelow", lambda n: next(picks))
    taken = {9}
    index = await status_list.allocate_index(Taken({5}), taken)
    assert index == 11 and 11 in taken


async def test_a_full_list_does_not_stop_issuance(monkeypatch, signing_key):
    monkeypatch.setattr(status_list.secrets, "randbelow", lambda n: 1)
    assert await status_list.allocate_index(Taken({1})) is None
    cred = issuer.issue_achievement_credential("c-3", "p-1", {"type": "FSPCompetitionResult"}, status_index=None)
    assert cred["credentialStatus"]["type"] == "FSPCredentialStatus" and issuer.verify_credential(cred)


class Rows:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class Db:
    def __init__(self, rows):
        self.rows = rows

    async def scalars(self, stmt):
        return Rows(self.rows)


async def test_the_public_route_sets_the_bits_of_revoked_credentials(signing_key):
    response = await public.status_list(1, Db([2, 7]))
    assert response.headers["cache-control"] == "public, max-age=300"
    doc = json.loads(response.body)
    raw = decode(doc["credentialSubject"]["encodedList"])
    assert is_set(raw, 2) and is_set(raw, 7) and not is_set(raw, 3)
    with pytest.raises(public.ApiError):
        await public.status_list(2, Db([]))
