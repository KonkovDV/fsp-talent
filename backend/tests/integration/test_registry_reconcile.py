"""Audit M-3: an annulled or corrected protocol line leaves the score; an outage removes nothing."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, select

from app.models import Result, VerifiableCredential
from app.services.fsp.mock import FSPParticipant, FSPResult
from app.services.profile import append_new_results, reconcile_results
from tests.integration.conftest import stamp, wipe_people
from tests.integration.test_search_order import _person


def _line(event: str, place: int, total: int = 40) -> FSPResult:
    return FSPResult(event_id=event, event_name=f"Соревнование {event}", discipline="security",
                     competition_status="regional", place=place, total_participants=total,
                     is_team=False, team_size=1, event_date=date(2026, 3, 1))


async def test_annulled_and_corrected_lines_are_applied(db):
    person = await _person(db, stamp(), 0)
    try:
        fsp_id = f"FSP{uuid.uuid4().hex[:8]}"
        tag = uuid.uuid4().hex[:6]
        a, b, c, d = (f"{tag}-{x}" for x in "abcd")
        first = FSPParticipant(fsp_id=fsp_id, display_name="Тест", region="Москва", birth_date=date(2000, 1, 1),
                               results=[_line(a, 1), _line(b, 2), _line(c, 30)])
        assert await append_new_results(db, person, first) == 3
        old_b = await db.scalar(select(Result.id).where(Result.participant_id == person.id, Result.event_id == b))

        # b annulled, c corrected from 30th to 3rd, d new.
        second = FSPParticipant(fsp_id=fsp_id, display_name="Тест", region="Москва", birth_date=date(2000, 1, 1),
                                results=[_line(a, 1), _line(c, 3), _line(d, 2)])
        assert await reconcile_results(db, person, second) == {"added": 1, "corrected": 1, "removed": 1}
        rows = {r.event_id: r.place for r in await db.scalars(select(Result).where(Result.participant_id == person.id))}
        assert rows == {a: 1, c: 3, d: 2}
        revoked = list(await db.scalars(select(VerifiableCredential).where(
            VerifiableCredential.participant_id == person.id, VerifiableCredential.revoked_at.is_not(None))))
        assert len(revoked) == 2 and all(vc.result_id is None for vc in revoked)
        assert old_b not in {r.id for r in await db.scalars(select(Result).where(Result.participant_id == person.id))}

        # A registry outage (empty answer) never wipes the history; a repeat changes nothing.
        empty = FSPParticipant(fsp_id=fsp_id, display_name="Тест", region="Москва", birth_date=date(2000, 1, 1))
        assert await reconcile_results(db, person, empty) == {"added": 0, "corrected": 0, "removed": 0}
        assert await reconcile_results(db, person, second) == {"added": 0, "corrected": 0, "removed": 0}
        await db.commit()
    finally:
        await db.rollback()
        await db.execute(delete(VerifiableCredential).where(VerifiableCredential.participant_id == person.id))
        await db.execute(delete(Result).where(Result.participant_id == person.id))
        await db.commit()
        await wipe_people([person.id])
