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
