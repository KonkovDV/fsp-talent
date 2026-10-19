"""Interview times stay in Moscow on the calendar, and the outcome moves P(accept) only for that company."""
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.services.interviews import calendar_text, moscow_start, still_ahead
from app.services.matching import CandidateFacts, NeedSpec, score


def test_calendar_writes_moscow_wall_time():
    start = moscow_start("2026-10-15", "14:00")
    text = calendar_text(uuid.UUID("11111111-1111-1111-1111-111111111111"), start, "online",
                         "https://meet.example/room", "Собеседование: backend")
    assert "DTSTART;TZID=Europe/Moscow:20261015T140000" in text
    assert "BEGIN:VCALENDAR" in text and "END:VCALENDAR" in text
    # 14:00 in Moscow is 11:00 UTC. The file must not stamp the start in UTC.
    assert "DTSTART:20261015T110000Z" not in text
    assert start.astimezone(UTC).hour == 11
    poisoned = calendar_text(uuid.UUID("22222222-2222-2222-2222-222222222222"), start, "online",
                             "комната\r\nSUMMARY:чужая встреча", "Собеседование")
    assert sum(1 for line in poisoned.split("\r\n") if line.startswith("SUMMARY:")) == 1


def test_a_meeting_that_already_started_cannot_be_chosen():
    start = moscow_start("2026-10-15", "14:00")
    assert still_ahead(start, datetime(2026, 10, 15, 10, 59, tzinfo=UTC))
    assert not still_ahead(start, datetime(2026, 10, 15, 11, 0, tzinfo=UTC))
    assert not still_ahead(start, datetime(2026, 10, 15, 12, 0, tzinfo=UTC))


def test_a_failed_interview_lowers_accept_and_no_interview_leaves_it():
    need = NeedSpec(salary_from=200_000, salary_to=220_000)
    person = CandidateFacts(role="backend", grade="middle", grade_source="assessed",
                            salary_from=300_000, salary_to=300_000, job_search="active")
    plain = score(need, person)
    failed = score(need, CandidateFacts(
        role="backend", grade="middle", grade_source="assessed",
        salary_from=300_000, salary_to=300_000, job_search="active", interview_outcome="failed"))
    missed = score(need, CandidateFacts(
        role="backend", grade="middle", grade_source="assessed",
        salary_from=300_000, salary_to=300_000, job_search="active", interview_outcome="no_show"))
    passed = score(need, CandidateFacts(
        role="backend", grade="middle", grade_source="assessed",
        salary_from=300_000, salary_to=300_000, job_search="active", interview_outcome="passed"))
    assert failed.score == plain.score == missed.score == passed.score
    assert failed.accept < plain.accept
    assert missed.accept < failed.accept
    assert passed.accept > plain.accept
    assert any(r.code == "INTERVIEW_FAILED" for r in failed.reasons)
    assert all(r.code != "INTERVIEW_PASSED" for r in plain.reasons)


def test_interview_slots_live_in_the_initial_migration():
    text = Path("alembic/versions/0001_initial.py").read_text(encoding="utf-8")
    assert "CREATE TABLE public.interview_slots" in text
    assert "interview_slots_actor" in text
    assert "uq_interview_slots_chosen" in text
    down = text.split("def downgrade", 1)[1]
    assert "DROP TABLE IF EXISTS" in down
