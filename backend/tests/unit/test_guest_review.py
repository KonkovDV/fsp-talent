"""The guest shortlist carries no identity and marks stay on the snapshot."""
import json

import pytest

from app.services.guest_review import apply_mark, fresh_token, marks_for_owner, public_seats, token_hash


def test_public_snapshot_drops_identity():
    seats, ids = public_seats([{
        "candidate_id": "pid-1",
        "role": "backend",
        "grade": "middle",
        "grade_source": "assessed",
        "region": "Новосибирск",
        "stack": ["Python"],
        "matched_skills": ["PostgreSQL"],
        "missing_skills": [],
        "why": ["Подтверждено тестом"],
        "resume_summary": "Иван Петров, ivan@example.com",
        "email": "ivan@example.com",
    }])
    blob = json.dumps(seats, ensure_ascii=False)
    assert "pid-1" not in blob
    assert "ivan@" not in blob
    assert "Петров" not in blob
    assert seats[0]["seat"] == 1 and seats[0]["role"] == "backend"
    assert ids == ["pid-1"]


def test_mark_stays_inside_the_snapshot():
    marks = apply_mark({}, 2, 1, "yes")
    assert marks == {"1": "yes"}
    with pytest.raises(ValueError):
        apply_mark(marks, 2, 3, "yes")
    with pytest.raises(ValueError):
        apply_mark(marks, 2, 1, "hire")


def test_owner_sees_marks_by_id_and_the_token_is_only_a_hash():
    owned = marks_for_owner(["pid-1", ""], {"1": "later", "2": "no"})
    assert owned == [{"candidate_id": "pid-1", "mark": "later"}]
    token, digest = fresh_token()
    assert digest == token_hash(token)
    assert token not in digest


async def test_a_mark_locks_the_snapshot_so_a_parallel_mark_is_not_lost(monkeypatch):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from app.api.v1 import public

    async def calm(*_args, **_kwargs):
        return False

    row = SimpleNamespace(title="Backend", seats=[{"seat": 1}, {"seat": 2}], marks={"1": "yes"},
                          expires_at=datetime.now(UTC) + timedelta(days=1))

    class Db:
        def __init__(self):
            self.sql = []

        async def scalar(self, stmt):
            self.sql.append(str(stmt))
            return row

        async def commit(self):
            pass

    monkeypatch.setattr(public, "too_many", calm)
    monkeypatch.setattr(public, "flag_modified", lambda *_args: None)
    db = Db()
    token, _ = fresh_token()
    await public.mark_public_review(token, public.GuestMarkIn(seat=2, mark="later"), db)
    assert "FOR UPDATE" in db.sql[0]
    assert row.marks == {"1": "yes", "2": "later"}
    await public.read_public_review(token, db)
    assert "FOR UPDATE" not in db.sql[1]
