"""The start-up rescore must see RLS-protected rows, or it wipes the resume stack from search."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select, update

from app.core.rescore_stale import rescore_stale
from app.core.rls import reset_rls, set_rls
from app.models import CandidateResume, DisciplineScore, ProfileSearchIndex, Result, VerifiableCredential
from app.services.fsp.mock import FSPParticipant
from app.services.profile import append_new_results, rebuild_profile
from app.services.scoring.engine import VERSION
from tests.integration.conftest import stamp, wipe_people
from tests.integration.test_registry_reconcile import _line
from tests.integration.test_search_order import _person


async def test_startup_rescore_keeps_the_resume_stack(db):
    person = await _person(db, stamp(), 0)
    pid = person.id
    try:
        fsp_id = f"FSP{uuid.uuid4().hex[:8]}"
        person.fsp_id = fsp_id
        await append_new_results(db, person, FSPParticipant(
            fsp_id=fsp_id, display_name="Тест", region="Москва", birth_date=date(2000, 1, 1),
            results=[_line(f"rls-{uuid.uuid4().hex[:6]}", 1)]))
        db.add(CandidateResume(participant_id=pid, specialization="backend", grade="middle", stack=["Zzqrustacean"]))
        await db.flush()
        await rebuild_profile(db, person)
        await db.execute(update(DisciplineScore).where(DisciplineScore.participant_id == pid)
                         .values(scoring_version="v3.2.0"))
        await db.commit()
        assert "Zzqrustacean" in (await db.get(ProfileSearchIndex, pid)).skills_text
        scope = set_rls(bypass=False)   # as in the container CMD: no request, no worker scope
        try:
            await rescore_stale()
        finally:
            reset_rls(scope)
        db.expire_all()
        assert "Zzqrustacean" in (await db.get(ProfileSearchIndex, pid)).skills_text
        stored = list(await db.scalars(select(DisciplineScore).where(DisciplineScore.participant_id == pid)))
        assert stored and {row.scoring_version for row in stored} == {VERSION}
    finally:
        await db.rollback()
        from sqlalchemy import delete
        await db.execute(delete(CandidateResume).where(CandidateResume.participant_id == pid))
        await db.execute(delete(VerifiableCredential).where(VerifiableCredential.participant_id == pid))
        await db.execute(delete(Result).where(Result.participant_id == pid))
        await db.commit()
        await wipe_people([pid])
