"""Skills passport: signed, anonymous, one live link per candidate, gone with the profile."""
import copy
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1 import passport as api
from app.api.v1 import public
from app.models import Participant, VerifiableCredential
from app.models.assessment import GradeConfirmation
from app.models.participant import Result, Skill
from app.services.passport import is_passport, issue_passport, passport_claims
from app.services.survey import SPECIALIZATIONS
from app.services.vc.issuer import verify_credential

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
PID = uuid.uuid4()


def grade(spec="backend", level="middle"):
    return SimpleNamespace(specialization=spec, grade=level, confirmed_at=NOW)


def skill(name, trust="test_confirmed"):
    return SimpleNamespace(name=name, trust_level=trust)


def result(place, total, year=2025, discipline="product", status="all_russian"):
    return SimpleNamespace(place=place, total_participants=total, event_date=date(year, 5, 1),
                           discipline=discipline, competition_status=status, event_name="Кубок Сибири")


def test_claims_keep_only_tested_evidence_and_no_event_titles():
    claims = passport_claims([grade()], [skill("SQL"), skill("Go", "self_reported"), skill("Python")],
                             [result(90, 100, 2024), result(1, 200, 2025)])
    assert claims["grades"] == [{"specialization": SPECIALIZATIONS["backend"], "grade": "middle",
                                 "confirmedOn": "2026-10-10"}]
    assert claims["testedSkills"] == ["Python", "SQL"]
    [fsp] = claims["fspResults"]
    assert fsp["results"] == 2 and fsp["bestBucket"] == "топ-1%" and fsp["lastYear"] == 2025
    assert "Кубок Сибири" not in str(claims)


def test_the_passport_is_signed_names_nobody_and_breaks_when_edited():
    pid = uuid.uuid4()
    credential = issue_passport(pid, passport_claims([grade()], [skill("SQL")], []))
    assert verify_credential(credential) and is_passport(credential)
    assert credential["credentialSubject"]["id"] == f"urn:uuid:{pid}"
    assert credential["credentialStatus"]["id"].endswith(f"/public/credentials/{pid}/status")
    forged = copy.deepcopy(credential)
    forged["credentialSubject"]["achievement"]["grades"][0]["grade"] = "lead"
    assert not verify_credential(forged)


class Rows:
    def __init__(self, items):
        self.items = items

    def __iter__(self):
        return iter(self.items)


class Db:
    def __init__(self, person, vcs=(), confirmations=(), skills=(), results=()):
        self.person, self.vcs = person, list(vcs)
        self.by_model = {GradeConfirmation: list(confirmations), Skill: list(skills), Result: list(results)}
        self.added, self.commits = [], 0

    async def get(self, model, ident, **kwargs):
        if model is Participant:
            return self.person if self.person and self.person.id == ident else None
        return next((v for v in self.vcs if v.id == ident), None)

    async def scalars(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is VerifiableCredential:
            return Rows([v for v in self.vcs if v.revoked_at is None])
        return Rows(self.by_model[entity])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, VerifiableCredential):
            self.vcs.append(obj)

    async def commit(self):
        self.commits += 1


def person(**kw):
    return SimpleNamespace(**{"id": PID, "deleted_at": None, "is_minor": False, **kw})


@pytest.fixture(autouse=True)
def no_limit(monkeypatch):
    async def never(*args, **kwargs):
        return False
    monkeypatch.setattr(api, "too_many", never)


async def test_a_new_passport_revokes_the_old_link():
    db = Db(person(), confirmations=[grade()], skills=[skill("SQL")])
    current = {"sub": str(PID)}
    first = await api.issue_my_passport(current, db)
    second = await api.issue_my_passport(current, db)
    assert first["id"] != second["id"] and second["url"].endswith(f"/passport/{second['id']}")
    old = await db.get(VerifiableCredential, uuid.UUID(first["id"]))
    assert old.revoked_at is not None
    seen = await api.public_passport(uuid.UUID(first["id"]), db)
    assert seen["revoked"] and not seen["valid"] and seen["signature"]
    live = await api.public_passport(uuid.UUID(second["id"]), db)
    assert live["valid"] and "display_name" not in str(live)


async def test_nothing_to_sign_minors_and_erased_profiles_get_no_passport():
    with pytest.raises(ApiError) as empty:
        await api.issue_my_passport({"sub": str(PID)}, Db(person(), skills=[skill("Go", "self_reported")]))
    assert empty.value.status_code == 409
    with pytest.raises(ApiError) as minor:
        await api.issue_my_passport({"sub": str(PID)}, Db(person(is_minor=True), confirmations=[grade()]))
    assert minor.value.status_code == 403
    db = Db(person(), confirmations=[grade()])
    issued = await api.issue_my_passport({"sub": str(PID)}, db)
    db.person.deleted_at = NOW
    with pytest.raises(ApiError) as gone:
        await api.public_passport(uuid.UUID(issued["id"]), db)
    assert gone.value.status_code == 404


async def test_a_protocol_credential_is_not_served_as_a_passport():
    plain = {"credentialSubject": {"achievement": {"type": ["Achievement"]}}}
    vc = SimpleNamespace(id=uuid.uuid4(), participant_id=PID, result_id=None, revoked_at=None,
                         issued_at=NOW, credential_json=plain)
    with pytest.raises(ApiError):
        await api.public_passport(vc.id, Db(person(), vcs=[vc]))
    assert not is_passport(vc.credential_json)
    assert public.is_passport is is_passport
