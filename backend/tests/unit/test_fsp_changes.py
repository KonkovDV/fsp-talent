"""Delta of the registry: a known event is not imported twice, and the cursor sees recent protocols."""
from datetime import date, datetime

from app.services.fsp.mock import DEMO, FSPResult, MockFSPAdapter
from app.services.profile import unseen_results


def test_unseen_results_skip_events_already_stored():
    person = DEMO["FSP001"]
    known = {person.results[0].event_id}
    fresh = unseen_results(known, person)
    assert person.results[0].event_id not in {row.event_id for row in fresh}
    assert len(fresh) == len(person.results) - 1


def test_demo_calendar_numbers_are_marked_as_demo():
    numbers = [row.ekp_number for row in DEMO["FSP001"].results]
    assert numbers and all(n and n.startswith("ЕКП-демо-") for n in numbers)


async def test_changes_since_includes_a_recent_protocol_and_skips_an_old_cutoff():
    adapter = MockFSPAdapter()
    recent = await adapter.changes_since(datetime(2025, 1, 1))
    assert "FSP001" in recent.fsp_ids
    future = await adapter.changes_since(datetime(2099, 1, 1))
    assert "FSP001" not in future.fsp_ids
    assert future.next_since.tzinfo is not None


async def test_the_cursor_moves_only_when_remember_is_called():
    from datetime import UTC, datetime

    from app.services.fsp.sync import CURSOR, remember_cursor

    class Redis:
        def __init__(self):
            self.store = {CURSOR: "2026-01-01T00:00:00+00:00"}

        async def set(self, key, value):
            self.store[key] = value

    redis = Redis()
    previous = redis.store[CURSOR]
    await remember_cursor(redis, None)
    assert redis.store[CURSOR] == previous
    await remember_cursor(redis, datetime(2026, 6, 1, tzinfo=UTC))
    assert redis.store[CURSOR].startswith("2026-06-01")


def test_result_without_calendar_number_stays_optional():
    row = FSPResult("E", "Имя", "algorithmic", "other", 1, 10, False, 1, date(2026, 1, 1))
    assert row.ekp_number is None
