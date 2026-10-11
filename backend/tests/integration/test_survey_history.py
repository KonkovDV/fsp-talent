"""TZ 2.1: every survey submit is kept as history, newest first; erase removes it."""
from sqlalchemy import func, select

from app.api.v1.candidates import SurveyIn, save_survey, survey_history
from app.models import Participant, SurveyHistory
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people


async def test_two_submits_make_two_history_rows(db):
    person = Participant(email=f"dbtest-survey-{stamp()}@example.com", display_name="Опрос",
                         password_hash=PASSWORD_HASH, email_verified_at=now(), is_minor=False,
                         is_visible=True, public_profile=False, region="Москва")
    db.add(person)
    await db.commit()
    me = {"sub": str(person.id)}
    try:
        await save_survey(SurveyIn(specialization="backend", declared_grade="junior", experience_years=1), me, db)
        await save_survey(SurveyIn(specialization="frontend", declared_grade="middle", experience_years=3), me, db)
        rows = await survey_history(20, me, db)
        assert [(r["specialization"], r["declared_grade"]) for r in rows] == [
            ("frontend", "middle"), ("backend", "junior")]
        assert rows[0]["experience_years"] == 3
        stored = await db.scalar(select(func.count()).select_from(SurveyHistory)
                                 .where(SurveyHistory.participant_id == person.id))
        assert stored == 2
    finally:
        await wipe_people([person.id])
