"""audit-3 P1-1 / P2-2: one employer-visibility rule, and the Python property agrees with the SQL predicate."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models import Participant
from app.services.search.pipeline import visible_in_search
from tests.integration.conftest import now, stamp, wipe_people
from tests.integration.test_search_order import _person

CASES = {
    "adult": {},
    "no_birth_date": {"birth_date": None},
    "minor_no_consent": {"birth_date": date(2012, 1, 1), "is_minor": True},
    "minor_with_consent": {"birth_date": date(2012, 1, 1), "is_minor": True, "minor_consent_given": True},
    "not_looking": {"job_search": "not_looking"},
    "hidden": {"is_visible": False},
    "deleted": {"deleted_at": "now"},
    "suspended": {"suspended_at": "now"},
}
SQL_ONLY_HIDDEN = {"deleted", "suspended"}   # account states the per-row property does not model


async def test_python_and_sql_visibility_agree(db):
    tag = stamp()
    people = {}
    pid: dict = {}
    try:
        for i, (name, change) in enumerate(CASES.items()):
            person = await _person(db, f"{tag}-vis", i)
            for key, value in change.items():
                setattr(person, key, now() if value == "now" else value)
            people[name] = person
        python = {name: p.discoverable for name, p in people.items()}
        pid = {name: p.id for name, p in people.items()}
        await db.commit()
        ids = set(pid.values())
        visible = set(await db.scalars(select(Participant.id).where(Participant.id.in_(ids), visible_in_search())))
        for name in CASES:
            sql = pid[name] in visible
            if name in SQL_ONLY_HIDDEN:
                assert not sql, name
            else:
                assert sql == python[name], (name, sql, python[name])
        assert {n for n in CASES if pid[n] in visible} == {"adult", "minor_with_consent"}
    finally:
        await db.rollback()
        await wipe_people(list(pid.values()) )
