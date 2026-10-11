"""ST P1: /leaderboard showed full names while /jury promises a public list without names."""
import uuid
from types import SimpleNamespace

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
