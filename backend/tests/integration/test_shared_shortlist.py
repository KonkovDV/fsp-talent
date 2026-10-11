"""Audit-5 A8: a shared need ranking never carries one company's exclusions to another company."""
from __future__ import annotations

from sqlalchemy import delete

from app.api.v1.needs import NeedParams, _matches_cached
from app.core.redis_client import get_redis
from app.models import CandidateBlock, Employer, Need
from app.services.exclusions import shared_scope
from tests.integration.conftest import PASSWORD_HASH, now, stamp, wipe_people
from tests.integration.test_search_order import _person


def _company(tag: str, name: str) -> Employer:
    return Employer(email=f"dbtest-hr-{name}-{tag}@example.com", company_name=f"Интеграция {name} {tag}",
                    password_hash=PASSWORD_HASH, email_verified_at=now(), industry="fintech")


async def test_a_block_by_one_company_does_not_leak_through_the_shared_cache(db):
    tag = stamp()
    person = await _person(db, tag, 2)                       # backend / middle
    pid = person.id
    plain, blocked = _company(tag, "a"), _company(tag, "b")
    db.add_all([plain, blocked])
    await db.flush()
    db.add(CandidateBlock(participant_id=pid, employer_id=blocked.id))
    needs = [Need(employer_id=c.id, title="backend", version=1) for c in (plain, blocked)]
    db.add_all(needs)
    await db.commit()
    eids = [plain.id, blocked.id]
    params = NeedParams(role="backend", grade="middle", grade_match="exact")
    try:
        redis = await get_redis()
        for key in await redis.keys("shortlist-shared:*"):
            await redis.delete(key)
        assert await shared_scope(db, plain.id, None) == "fintech"
        assert await shared_scope(db, blocked.id, None) is None
        first = await _matches_cached(db, needs[0], params, 200, 0)
        assert str(pid) in {i["candidate_id"] for i in first["items"]}
        second = await _matches_cached(db, needs[1], params, 200, 0)
        assert str(pid) not in {i["candidate_id"] for i in second["items"]}
    finally:
        await db.rollback()
        await db.execute(delete(CandidateBlock).where(CandidateBlock.participant_id == pid))
        await db.execute(delete(Need).where(Need.employer_id.in_(eids)))
        await db.commit()
        await wipe_people([pid], eids)
