"""Ready-made jury candidates: `python -m seed.demo_ready`. Idempotent, safe on a running stand.

jury1…jury5 keep an empty survey: the show walks the candidate path from the first step (docs/INSTALL.md).
jury6…jury10 start ready: an adult birth date, a filled survey, a grade confirmed by one real test session,
so a juror can open «Вакансии под профиль» and apply at once. A graded vacancy waits for a test-confirmed
grade (ТЗ 2.1, #289, SDK-03), which is why the grade here comes from the test service, not from a field.
An account that already has a confirmed grade is left as it is.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import CategoryAssignment, Participant, Skill
from app.services.profile import rebuild_profile
from seed.generate_seed import JURY_BIRTH
from seed.topup_public import SKILLS, sit_like_a_person

# (account, specialization, grade, years). Backend has the most demo vacancies, so most ready accounts are backend.
READY = (
    ("jury6@demo.talent", "backend", "middle", 3),
    ("jury7@demo.talent", "backend", "middle", 3),
    ("jury8@demo.talent", "backend", "junior", 1),
    ("jury9@demo.talent", "security", "middle", 3),
    ("jury10@demo.talent", "backend", "middle", 4),
)


async def make_ready(db) -> dict:
    by_email = {(p.email or "").strip().lower(): p
                for p in await db.scalars(select(Participant).where(Participant.email.is_not(None)))}
    ready = skipped = failed = 0
    for email, spec, grade, years in READY:
        person = by_email.get(email)
        if person is None:
            continue
        if person.assessed_grade:
            category = await db.scalar(select(CategoryAssignment).where(
                CategoryAssignment.participant_id == person.id))
            if category is None or category.grade_source != "assessed":
                await rebuild_profile(db, person)
                await db.commit()
            skipped += 1
            continue
        now = datetime.now(UTC)
        if person.birth_date is None:
            person.birth_date, person.is_minor = JURY_BIRTH, False
        person.specialization, person.declared_grade, person.experience_years = spec, grade, years
        person.work_goal, person.industry, person.survey_at = "job", "fintech", now
        person.region = person.region or "Новосибирск"
        person.work_formats = person.work_formats or ["remote", "hybrid"]
        if not list(await db.scalars(select(Skill.id).where(Skill.participant_id == person.id))):
            for name in SKILLS[spec]:
                db.add(Skill(participant_id=person.id, name=name, raw_name=name,
                             trust_level="self_reported", confirmed=True))
        await db.flush()
        await rebuild_profile(db, person)
        await db.commit()
        try:
            ok = await sit_like_a_person(db, person, grade, email, strong=True)
            await rebuild_profile(db, person)  # the API rebuilds after a test; the category reads «подтверждён»
            await db.commit()
        except Exception as exc:  # one failed sitting must not stop the others
            await db.rollback()
            print(f"demo_ready test skipped {email}: {type(exc).__name__}")
            ok = False
        ready += int(ok)
        failed += int(not ok)
    return {"ready": ready, "skipped": skipped, "failed": failed}


async def main_async() -> dict:
    from app.core.rls import bypass_rls
    bypass_rls()
    async with AsyncSessionLocal() as db:
        result = await make_ready(db)
    print(f"demo_ready ready={result['ready']} already={result['skipped']} failed={result['failed']}")
    return result


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
