"""F24b: a finished test keeps the share of right answers per profile skill, passed or not."""
import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from app.services import assessment, cat


def test_tallies_keep_every_tag_with_counts():
    rows = [(("Python",), True), (("Python", "SQL"), False), (("Python",), True)]
    assert cat.skill_tallies(rows) == {"Python": (2, 3), "SQL": (0, 1)}
    assert cat.skill_scores(rows) == {"Python": 2 / 3}


class _Db:
    def __init__(self, rows):
        self.rows, self.added = rows, []

    async def scalar(self, stmt):
        name = next(v for k, v in stmt.compile().params.items() if k.startswith("name"))
        return self.rows.get(name)

    def add(self, obj):
        self.added.append(obj)


def _item(skill, ok):
    return SimpleNamespace(skills=[skill], is_correct=ok)


def test_failed_check_is_stored_on_the_profile_skill_and_creates_nothing_new():
    py = SimpleNamespace(name="Python", trust_level="self_reported", confirmed=True, confirmed_at=None,
                         source_quote=None, test_share=None, test_items=None, tested_at=None)
    sql = SimpleNamespace(name="SQL", trust_level="self_reported", confirmed=True, confirmed_at=None,
                          source_quote=None, test_share=None, test_items=None, tested_at=None)
    db = _Db({"Python": py, "SQL": sql})
    answered = [_item("Python", True), _item("Python", False), _item("Python", False),
                _item("SQL", True), _item("SQL", True), _item("SQL", True), _item("SQL", True),
                _item("Go", False), _item("Go", False), _item("Go", False)]
    now = datetime(2026, 10, 11, tzinfo=UTC)
    session = SimpleNamespace(participant_id="p")
    confirmed = asyncio.run(assessment._confirm_skills(db, session, answered, now))
    assert confirmed == [("SQL", 1.0)]
    # Checked, not confirmed: the share is kept, the declaration stays a declaration.
    assert (py.test_share, py.test_items, py.tested_at, py.trust_level) == (0.3333, 3, now, "self_reported")
    assert (sql.test_share, sql.test_items, sql.trust_level) == (1.0, 4, "test_confirmed")
    # Go is not a catalog skill: a failed check adds no skill.
    assert [row.name for row in db.added] == []


def test_a_failed_catalog_skill_stays_a_claim_and_blocks_the_prize():
    from app.services.fsp_skills import apply_fsp_skills

    db = _Db({})
    answered = [_item("Machine Learning", False)] * 3
    now = datetime(2026, 10, 18, tzinfo=UTC)
    session = SimpleNamespace(participant_id="p")
    confirmed = asyncio.run(assessment._confirm_skills(db, session, answered, now))
    assert confirmed == []
    assert len(db.added) == 1
    row = db.added[0]
    assert (row.name, row.trust_level, row.confirmed, row.test_items) == (
        "Machine Learning", "self_reported", True, 3)
    kept = apply_fsp_skills(
        {"Machine Learning": "self_reported"}, frozenset({"Machine Learning"}), frozenset({"Machine Learning"}))
    assert kept["Machine Learning"] == "self_reported"
