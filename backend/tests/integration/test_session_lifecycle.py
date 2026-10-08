"""A grade session runs from the first item to a category."""
import uuid

from sqlalchemy import select

from app.api.v1.assessment import (
    PracticeAnswerIn,
    PracticeStartIn,
    StartIn,
    _start_test,
    abandon_session,
    active,
    blueprint,
    cooldown_status,
    get_session,
    practice_answer,
    practice_start,
    practice_weekly,
    review,
    session_history,
)
from app.models import CategoryAssignment, Participant, PracticeAttempt, Skill
from app.services.assessment import answer_item, item_token, start_session
from app.services.profile import rebuild_profile
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def test_session_confirms_a_grade(db):
    tag = stamp()
    person = Participant(
        email=f"dbtest-session-{tag}@example.com",
        display_name="Сессия",
        password_hash=PASSWORD_HASH,
        email_verified_at=now(),
        is_minor=False,
        is_visible=True,
        public_profile=False,
        specialization="backend",
        declared_grade="junior",
        experience_years=1,
        job_search="active",
        survey_at=now(),
        work_goal="job",
        region="Новосибирск",
    )
    db.add(person)
    await db.flush()
    db.add(Skill(
        participant_id=person.id, name="Python", raw_name="Python",
        trust_level="self_reported", confirmed=True))
    await db.flush()
    await rebuild_profile(db, person)
    await db.commit()
    try:
        session, item = await start_session(db, person.id, "backend", "junior")
        await db.commit()
        finished = None
        for _ in range(24):
            token = item_token(session.id, item.seq, item.id)
            if item.typed:
                session, nxt, finished = await answer_item(
                    db, session.id, person.id, token, answer_text=item.options[item.correct_index])
            else:
                session, nxt, finished = await answer_item(
                    db, session.id, person.id, token, answer_index=item.correct_index)
            await db.commit()
            if finished is not None:
                break
            item = nxt
        assert finished is not None
        assert session.status == "completed"
        assert session.items_count >= 8
        await rebuild_profile(db, person)
        await db.commit()
        cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == person.id))
        assert cat is not None
        assert cat.primary_role == "backend"
        assert cat.grade == "junior"
        assert cat.grade_source == "assessed"
        current = {"sub": str(person.id)}
        assert (await blueprint())["specializations"]["backend"]["families"]
        assert (await cooldown_status("backend", current, db))["locked"] is False
        assert await active(current, db) is None
        opened = await get_session(session.id, current, db)
        assert opened.status == "completed" and opened.result is not None
        assert (await session_history(20, 0, current, db))["items"]
        assert (await review(session.id, current, db))["items"]
        express = await _start_test(StartIn(target_grade="junior", mode="express"), current, db)
        dropped = await abandon_session(uuid.UUID(express.session_id), current, db)
        assert dropped.status == "abandoned"
        weekly = await practice_weekly(current, db)
        assert weekly is None or "vacancy_id" in weekly
        started = await practice_start(PracticeStartIn(topic="python"), current, db)
        attempt_id = uuid.UUID(started["id"])
        row = await db.get(PracticeAttempt, attempt_id)
        assert row is not None
        if started["answer_mode"] == "number":
            body = PracticeAnswerIn(answer_text=str(row.options[row.correct_index]))
        else:
            body = PracticeAnswerIn(answer_index=row.correct_index)
        checked = await practice_answer(attempt_id, body, current, db)
        assert checked["answered"] is True
    finally:
        await wipe_people([person.id])
