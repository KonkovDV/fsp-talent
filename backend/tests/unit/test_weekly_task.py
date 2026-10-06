"""Task of the week (TZ 2.1): the same vacancy for a candidate all week, a fresh pick the next week."""
import uuid
from datetime import UTC, datetime, timedelta

from app.services.practice import pick_weekly, week_start
from app.services.search.pipeline import days_ago

MONDAY = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
VACANCIES = [uuid.UUID(int=i) for i in range(1, 9)]


def test_pick_is_stable_within_a_week():
    person = uuid.uuid4()
    picks = {pick_weekly(VACANCIES, person, MONDAY + timedelta(days=d, hours=h)) for d in range(7) for h in (0, 13)}
    assert len(picks) == 1


def test_pick_moves_between_weeks_and_people():
    person = uuid.uuid4()
    by_week = {pick_weekly(VACANCIES, person, MONDAY + timedelta(weeks=w)) for w in range(12)}
    assert len(by_week) >= 3
    by_person = {pick_weekly(VACANCIES, uuid.uuid4(), MONDAY) for _ in range(40)}
    assert len(by_person) >= 4


def test_pick_ignores_list_order_and_handles_no_vacancies():
    person = uuid.uuid4()
    assert pick_weekly(VACANCIES, person, MONDAY) == pick_weekly(list(reversed(VACANCIES)), person, MONDAY)
    assert pick_weekly([], person, MONDAY) is None


def test_week_starts_on_monday_midnight_utc():
    assert week_start(datetime(2026, 10, 11, 23, 59, tzinfo=UTC)) == datetime(2026, 10, 5, tzinfo=UTC)
    assert week_start(MONDAY) == datetime(2026, 10, 5, tzinfo=UTC)


def test_freshness_reads_as_words():
    assert days_ago(MONDAY, MONDAY + timedelta(hours=3)) == "сегодня"
    assert days_ago(MONDAY, MONDAY + timedelta(days=1, hours=1)) == "вчера"
    assert days_ago(MONDAY, MONDAY + timedelta(days=12)) == "12 дн. назад"
