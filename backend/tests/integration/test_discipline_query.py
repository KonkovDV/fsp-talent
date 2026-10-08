"""A security need must not pay the query factor for a robotics result."""
from __future__ import annotations

import uuid

from sqlalchemy import delete

from app.models import Skill
from app.models.profile import DisciplineScore
from app.services.matching import NeedSpec
from app.services.profile import rebuild_profile
from app.services.search.pipeline import search_candidates
from tests.integration.conftest import stamp, wipe_people
from tests.integration.test_search_order import _person


def _score(person_id, discipline: str, lcb: float) -> DisciplineScore:
    return DisciplineScore(
        participant_id=person_id, discipline=discipline, score=lcb + 0.1, sigma=0.1, lcb=lcb,
        confidence=0.8, events_count=2, team_events_count=0, top_event_ids=[], scoring_version="v3.2.0",
    )


async def test_a_security_need_does_not_pay_the_query_for_robotics(db):
    tag = stamp()
    people = []
    try:
        security = await _person(db, tag + "s", 0)
        robotics = await _person(db, tag + "r", 1)
        for person in (security, robotics):
            person.specialization = "security"
            person.declared_grade = "middle"
            person.fsp_id = f"FSP{uuid.uuid4().hex[:8]}"
            person.salary_from_gross = 150_000
            person.salary_to_gross = 180_000
            person.experience_years = 4
        await db.execute(delete(Skill).where(Skill.participant_id.in_([security.id, robotics.id])))
        for person in (security, robotics):
            db.add(Skill(
                participant_id=person.id, name="Python", raw_name="Python",
                trust_level="test_confirmed", confirmed=True))
        await db.flush()
        for person in (security, robotics):
            await rebuild_profile(db, person)
        db.add(_score(security.id, "security", 0.5))
        db.add(_score(robotics.id, "robotics", 0.6))
        await db.commit()
        people = [security, robotics]

        result = await search_candidates(
            db, q="python", skills=["Python"],
            need=NeedSpec(role="security", grade="middle", skills=("Python",), text=True),
            limit=20,
        )
        cards = {
            uuid.UUID(card["candidate_id"]): card
            for card in result["items"]
            if uuid.UUID(card["candidate_id"]) in {security.id, robotics.id}
        }
        assert set(cards) == {security.id, robotics.id}
        order = [
            uuid.UUID(card["candidate_id"]) for card in result["items"]
            if uuid.UUID(card["candidate_id"]) in cards
        ]
        assert order.index(security.id) < order.index(robotics.id)

        def text_value(card) -> float:
            return next(factor["value"] for factor in card["match"]["factors"] if factor["key"] == "text")

        assert abs(text_value(cards[security.id]) - text_value(cards[robotics.id])) < 1e-9
        security_why = " ".join(cards[security.id]["why"])
        robotics_why = " ".join(cards[robotics.id]["why"])
        assert "Программирование систем ИБ" in security_why
        assert "0,50" in security_why
        assert "учтено с весом 0,5" in robotics_why
        assert "0,30" in robotics_why
    finally:
        await wipe_people([person.id for person in people])
