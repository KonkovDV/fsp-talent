"""Additive top-up of the public showcase: `python -m seed.topup_public`.

Public rankings and the bank hide a cell with fewer than BANK_MIN (5) people. On the stand only
37 of 256 profiles had a public card, an adult birth date and a consent to distribution, so every
public category was empty. This command only ADDS fictional adults «public-<role>-<grade>-NN@demo.talent»
until each key cell has TARGET public people who passed the test. It never deletes or rewrites an
existing row, so it is safe on a running stand; a second run adds nothing. The k-anonymity threshold
and the public filter stay as they are.
"""
from __future__ import annotations

import asyncio
import random
import secrets
from datetime import UTC, date, datetime

from sqlalchemy import and_, func, select

from app.api.v1.public import _public_filter
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password, verify_password
from app.legal import documents
from app.models import CategoryAssignment, Consent, GradeConfirmation, Participant, Skill
from app.services.identity import active_consent
from app.services.profile import rebuild_profile
from app.services.search.pipeline import BANK_MIN, visible_in_search
from seed.generate_seed import (
    _SHOWCASE_SKILLS,
    DEMO_PASSWORD,
    JURY_BIRTH,
    SHOWCASE_CORE,
    SHOWCASE_SPECS,
    _consents,
    _refuse_production,
)

TARGET = 6
PREFIX = "public-"
BIRTH = date(1996, 3, 1)
# DoR-10 also names «data»: the seed's showcase has no data row, so its skills live here.
SPECS = (*SHOWCASE_SPECS, "data")
SKILLS = {**_SHOWCASE_SKILLS, "data": ["Python", "SQL", "Airflow", "Spark"]}
CELLS = tuple((spec, grade) for spec in SPECS for grade in SHOWCASE_CORE)


def unusable_password_hash() -> str:
    """Nobody knows it: a visitor cannot sign in as a synthetic profile and delete it to empty a cell."""
    return hash_password(secrets.token_urlsafe(32))


def missing_for(counts: dict[tuple[str, str], int], target: int = TARGET) -> list[tuple[str, str, int]]:
    """Cells below target and how many people each needs. Never negative, never above target."""
    assert target >= BANK_MIN
    return [(spec, grade, target - counts.get((spec, grade), 0))
            for spec, grade in CELLS if counts.get((spec, grade), 0) < target]


async def public_counts(db) -> dict[tuple[str, str], int]:
    """The same set the public category ranking counts (public.category_ranking)."""
    rows = (await db.execute(
        select(GradeConfirmation.specialization, GradeConfirmation.grade,
               func.count(func.distinct(Participant.id)))
        .join(Participant, Participant.id == GradeConfirmation.participant_id)
        .join(CategoryAssignment, and_(
            CategoryAssignment.participant_id == Participant.id,
            CategoryAssignment.primary_role == GradeConfirmation.specialization,
            CategoryAssignment.grade == GradeConfirmation.grade))
        .where(GradeConfirmation.p_pass.is_not(None), visible_in_search(), *_public_filter())
        .group_by(GradeConfirmation.specialization, GradeConfirmation.grade))).all()
    return {(spec, grade): int(n) for spec, grade, n in rows}


async def backfill_jury(db) -> int:
    """Older stands were seeded before jurors had a birth date (887401f): adult-only actions and
    /vacancies/for-me stayed empty. Fill only what is missing; never overwrite a set field."""
    fixed = 0
    now = datetime.now(UTC)
    wanted = {f"jury{n}@demo.talent" for n in range(1, 11)}
    for person in await db.scalars(select(Participant).where(Participant.email.is_not(None))):
        if (person.email or "").strip().lower() not in wanted:
            continue
        changed = False
        if person.birth_date is None:
            person.birth_date, person.is_minor, changed = JURY_BIRTH, False, True
        for doc in documents().values():
            if doc.required and "participant" in doc.roles and \
                    await active_consent(db, "participant", person.id, doc.kind) is None:
                db.add(Consent(subject_type="participant", subject_id=person.id, kind=doc.kind,
                               version=doc.version, sha256=doc.sha256, given_at=now))
                changed = True
        fixed += int(changed)
    await db.commit()
    return fixed


async def sit_like_a_person(db, person: Participant, grade: str, email: str) -> bool:
    """A real session through the service, but not a perfect one: each answer is right with a share drawn
    per profile (seeded by the address), so places inside a category differ instead of six ties at 100 %."""
    from app.services import assessment
    rng = random.Random(email)
    share = rng.uniform(0.5, 0.85)
    session, item = await assessment.start_session(db, person.id, person.specialization, grade, code_language="python")
    for _ in range(25):
        token = assessment.item_token(session.id, item.seq, item.id)
        right = rng.random() < share
        n = len(item.options or []) or 1
        pick = item.correct_index if right else (item.correct_index + 1) % n
        if item.typed:
            value = int(item.options[item.correct_index])
            session, item, finished = await assessment.answer_item(
                db, session.id, person.id, token, answer_text=str(value if right else value + 1))
        else:
            session, item, finished = await assessment.answer_item(db, session.id, person.id, token, pick)
        if finished is not None:
            break
    await db.refresh(person)
    return person.assessed_grade == grade


async def relock_synthetic(db, password_hash: str) -> int:
    """Profiles an earlier top-up created with the printed demo password get an unusable one."""
    count = 0
    for person in await db.scalars(select(Participant).where(Participant.email.is_not(None))):
        email = (person.email or "").lower()
        if email.startswith(PREFIX) and email.endswith("@demo.talent") and person.password_hash \
                and verify_password(DEMO_PASSWORD, person.password_hash):
            person.password_hash = password_hash
            person.token_epoch = int(person.token_epoch or 0) + 1
            count += 1
    await db.commit()
    return count


async def topup(target: int = TARGET) -> dict:
    from app.core.rls import bypass_rls
    bypass_rls()
    async with AsyncSessionLocal() as db:
        jury_fixed = await backfill_jury(db)
        before = await public_counts(db)
        # Emails are ciphertext in the database: find our own rows in Python.
        ours = [p.email.lower() for p in await db.scalars(select(Participant).where(Participant.email.is_not(None)))
                if (p.email or "").lower().startswith(PREFIX) and p.email.lower().endswith("@demo.talent")]
        password_hash = unusable_password_hash()
        relocked = await relock_synthetic(db, password_hash)
        dist = documents()["pd_distribution"]
        added = passed = 0
        for spec, grade, need in missing_for(before, target):
            n = 0
            while need > 0 and n < target * 4:
                n += 1
                email = f"{PREFIX}{spec}-{grade}-{n:02d}@demo.talent"
                if email in ours:
                    continue
                now = datetime.now(UTC)
                person = Participant(
                    email=email, display_name=f"Публичный {spec} {grade} {n:02d}", region="Новосибирск",
                    birth_date=BIRTH, is_minor=False, is_visible=True, public_profile=True,
                    experience_years={"junior": 1, "middle": 3, "senior": 6}[grade], declared_grade=grade,
                    password_hash=password_hash, email_verified_at=now, specialization=spec,
                    industry="fintech", work_goal="job", survey_at=now, job_search="open")
                db.add(person)
                await db.flush()
                for name in SKILLS[spec]:
                    db.add(Skill(participant_id=person.id, name=name, raw_name=name,
                                 trust_level="self_reported", confirmed=True))
                _consents(db, "participant", person.id, now)
                db.add(Consent(subject_type="participant", subject_id=person.id, kind=dist.kind,
                               version=dist.version, sha256=dist.sha256, given_at=now))
                await rebuild_profile(db, person)
                await db.commit()
                added += 1
                try:
                    ok = await sit_like_a_person(db, person, grade, email)
                except Exception as exc:  # one failed sitting must not stop the top-up
                    await db.rollback()
                    print(f"topup test skipped {email}: {type(exc).__name__}")
                    continue
                await db.commit()
                if ok:
                    passed += 1
                    need -= 1
        after = await public_counts(db)
    short = [f"{s}/{g}={after.get((s, g), 0)}" for s, g in CELLS if after.get((s, g), 0) < BANK_MIN]
    print(f"topup_public jury_fixed={jury_fixed} relocked={relocked} added={added} passed={passed} "
          f"cells_below_{BANK_MIN}={len(short)} {' '.join(short)}")
    return {"jury_fixed": jury_fixed, "relocked": relocked, "added": added, "passed": passed,
            "before": before, "after": after}


def main() -> None:
    _refuse_production()
    asyncio.run(topup())


if __name__ == "__main__":
    main()
