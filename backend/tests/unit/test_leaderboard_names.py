"""ST P1: /leaderboard showed full names while /jury promises a public list without names."""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import public


def test_the_handle_has_no_name_and_is_stable():
    pid = uuid.UUID("3f2a9c00-0000-4000-8000-000000000001")
    assert public.public_handle(pid) == "Участник 3F2A"
    assert public.public_handle(str(pid)) == public.public_handle(pid)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Db:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _query):
        return _Result(self.rows)


async def test_leaderboard_rows_carry_the_handle_not_the_name():
    pid = uuid.uuid4()
    ds = SimpleNamespace(participant_id=pid, discipline="algorithmic", score=0.7, lcb=0.5, best_rank="КМС")
    person = SimpleNamespace(display_name="Алексей Кузнецов", region="Казань")
    rows = await public.get_leaderboard(discipline="algorithmic", limit=20, db=_Db([(ds, None, person)]))
    assert rows[0]["display_name"] == public.public_handle(pid)
    assert "Алексей" not in str(rows)


async def test_leaderboard_rows_carry_no_participant_id():
    """ST-03: the id in a row opened /p/{id}, and that page showed the name: one step from «no names» to the name."""
    pid = uuid.uuid4()
    ds = SimpleNamespace(participant_id=pid, discipline="algorithmic", score=0.7, lcb=0.5, best_rank="КМС")
    person = SimpleNamespace(display_name="Алексей Кузнецов", region="Казань")
    rows = await public.get_leaderboard(discipline=None, limit=20, db=_Db([(ds, None, person)]))
    assert "participant_id" not in rows[0]
    assert str(pid) not in str(rows) and str(pid).replace("-", "") not in str(rows)


class _ProfileDb:
    def __init__(self, person):
        self.person = person
        self.queries = []

    async def scalar(self, query):
        self.queries.append(query)
        return self.person


def _sql(query) -> str:
    from sqlalchemy.dialects import postgresql
    return str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


async def test_named_page_only_for_those_who_opened_it():
    """ST-04: an id from the blind HR search opens a name only when the person turned the public page on."""
    pid = uuid.uuid4()
    opted_in = SimpleNamespace(
        id=pid, display_name="Алексей Кузнецов", region="Казань", skills=[], discipline_scores=[], category=None)
    db = _ProfileDb(opted_in)
    card = await public.get_public_profile(public.public_ref(pid), db=db)
    assert card["display_name"] == "Алексей Кузнецов"
    sql = _sql(db.queries[0])
    assert "public_profile IS true" in sql and "pd_distribution" in sql and "withdrawn_at IS NULL" in sql
    # Without the toggle there is no page at all: neither the name nor the pseudonym with the data.
    for endpoint in (public.get_public_profile, public.public_profile_pdf):
        with pytest.raises(HTTPException) as err:
            await endpoint(public.public_ref(pid), db=_ProfileDb(None))
        assert err.value.status_code == 404


async def test_the_search_id_opens_no_public_page():
    """SEC3-01 / ST-04: the candidate_id of the blind HR card is the participant id. It is not a public ref."""
    pid = uuid.uuid4()
    person = SimpleNamespace(id=pid, display_name="Алексей Кузнецов", region="Казань", skills=[],
                             discipline_scores=[], category=None)
    for raw in (str(pid), pid.hex, str(pid).upper()):
        for endpoint in (public.get_public_profile, public.public_profile_pdf, public.get_credentials):
            db = _ProfileDb(person)
            with pytest.raises(HTTPException) as err:
                await endpoint(raw, db=db)
            assert err.value.status_code == 404 and db.queries == []
    ref = public.public_ref(pid)
    assert ref != str(pid) and pid.hex not in ref and public.participant_from_ref(ref) == pid
    card = await public.get_public_profile(ref, db=_ProfileDb(person))
    assert card["id"] == ref and str(pid) not in str(card)


def test_public_credentials_hide_the_subject_id():
    pid = uuid.uuid4()
    doc = {"id": "urn:uuid:c", "credentialSubject": {"id": f"urn:uuid:{pid}", "achievement": {"place": 1}}}
    shown = public._without_subject_id(doc)
    assert str(pid) not in str(shown) and shown["credentialSubject"]["achievement"] == {"place": 1}
    assert doc["credentialSubject"]["id"] == f"urn:uuid:{pid}"
