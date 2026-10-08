"""Fifty synthetic people: the search order is the order from matching.score."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models import CategoryAssignment, Participant, Skill
from app.services.matching import CandidateFacts, NeedSpec
from app.services.matching import score as match_score
from app.services.profile import rebuild_profile
from app.services.search.pipeline import bank_grid, order_pool, search_candidates
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people

GRADES = ("intern", "junior", "middle", "senior", "lead")
SKILLS = ("Python", "PostgreSQL", "FastAPI", "Docker", "Redis")


async def _person(db, tag: str, index: int) -> Participant:
    grade = GRADES[index % len(GRADES)]
    person = Participant(
        email=f"dbtest-{tag}-{index:02d}@example.com",
        display_name=f"Профиль {index:02d}",
        password_hash=PASSWORD_HASH,
        email_verified_at=now(),
        is_minor=False,
        is_visible=True,
        public_profile=False,
        specialization="backend",
        declared_grade=grade,
        experience_years=index % 9,
        salary_from_gross=80_000 + index * 2_000,
        salary_to_gross=120_000 + index * 2_000,
        job_search="active",
        survey_at=now(),
        work_goal="job",
        region="Новосибирск",
        industry="fintech",
    )
    db.add(person)
    await db.flush()
    for name in SKILLS[: 1 + (index % len(SKILLS))]:
        trust = "test_confirmed" if index % 3 == 0 else "self_reported"
        db.add(Skill(
            participant_id=person.id, name=name, raw_name=name, trust_level=trust, confirmed=True))
    await db.flush()
    await rebuild_profile(db, person)
    return person


async def test_search_order_matches_the_score(db):
    tag = stamp()
    people: list[Participant] = []
    try:
        for index in range(50):
            people.append(await _person(db, tag, index))
        await db.commit()
        need = NeedSpec(
            role="backend", grade="middle", skills=("Python", "PostgreSQL"),
            salary_from=100_000, salary_to=180_000)
        result = await search_candidates(
            db, skills=["Python", "PostgreSQL"], need=need, limit=50, offset=0)
        ours = {person.id for person in people}
        seen = [uuid.UUID(card["candidate_id"]) for card in result["items"] if uuid.UUID(card["candidate_id"]) in ours]
        assert len(seen) >= 20
        facts = {}
        for pid in seen:
            person = await db.get(Participant, pid)
            cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == pid))
            skills = {
                row.name: row.trust_level
                for row in await db.scalars(select(Skill).where(Skill.participant_id == pid, Skill.confirmed.is_(True)))
            }
            facts[pid] = CandidateFacts(
                role=cat.primary_role if cat else None,
                grade=cat.grade if cat else None,
                grade_source=cat.grade_source if cat else None,
                skills=skills,
                industry=person.industry if person else None,
                job_search=(person.job_search if person else None) or "open",
                salary_from=person.salary_from_gross if person else None,
                salary_to=person.salary_to_gross if person else None,
            )
        scores = {pid: match_score(need, facts[pid]).score for pid in seen}
        cards = {uuid.UUID(card["candidate_id"]): card["match"]["score"] for card in result["items"]}
        assert all(abs(cards[pid] - scores[pid]) < 1e-9 for pid in seen)
        expect = order_pool(seen, scores, {}, {})
        # Equal scores are ordered by the fused rank, then LCB, then id. The score sequence matches.
        assert [scores[pid] for pid in seen] == [scores[pid] for pid in expect]
        grid = await bank_grid(db)
        assert grid["cells"]
    finally:
        await wipe_people([person.id for person in people])
