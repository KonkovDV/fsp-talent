"""Idempotent demo data.

Logins (password demo12345): candidates fsp001@demo.talent, fsp002@demo.talent (FSP linked) and
nofsp@demo.talent (no FSP history); employer hr@sibcode.demo. Companies are fictional.
"""
import asyncio
import random
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.legal import documents
from app.models import Consent, Employer, Participant, Skill, Vacancy
from app.seed.questions import seed_questions
from app.services.categorization import DISCIPLINE_ROLE_MAP
from app.services.fsp.mock import MockFSPAdapter
from app.services.profile import ingest_from_fsp, rebuild_profile
from app.services.survey import INDUSTRIES

SKILLS = {
    "algorithmic": ["Python", "C++", "Algorithms", "Go", "Rust"],
    "product": ["TypeScript", "React", "Node.js", "PostgreSQL", "Docker"],
    "security": ["Pentesting", "CTF", "Linux", "Web Security", "Python"],
    "bas": ["C++", "Python", "PX4/ArduPilot", "ROS", "STM32"],
    "robotics": ["C++", "ROS", "Python", "Arduino", "Computer Vision"],
}
# Fictional companies: a demo must not look like a real employer is hiring here.
EMPLOYERS = [
    ("Сибирский код", "hr@sibcode.demo"), ("Квантум Лаб", "hr@quantumlab.demo"),
    ("Безопасный периметр", "hr@perimeter.demo"), ("Облачный кит", "hr@cloudwhale.demo"),
    ("РобоТех Урал", "hr@robotech.demo"),
]
DEMO_PASSWORD = "demo12345"
SPEC_OF = {"FSP001": "backend", "FSP002": "security"}
NO_FSP_DEMO = ("nofsp@demo.talent", "Ирина Смирнова", "Казань", 2, "middle",
               ["Python", "Django", "PostgreSQL", "Docker", "Redis"])


def _consents(db, subject_type: str, subject_id, now: datetime) -> None:
    for doc in documents().values():
        if doc.required and subject_type in doc.roles:
            db.add(Consent(subject_type=subject_type, subject_id=subject_id, kind=doc.kind, version=doc.version,
                           sha256=doc.sha256, given_at=now))
DEMOS = {
    "FSP001": (["Python", "Go", "FastAPI", "PostgreSQL", "Algorithms", "Docker"], 3),
    "FSP002": (["Pentesting", "CTF", "Linux", "Web Security", "Python"], 4),
}


async def main() -> None:
    adapter = MockFSPAdapter()
    async with AsyncSessionLocal() as db:
        password_hash = hash_password(DEMO_PASSWORD)
        now = datetime.now(UTC)
        employers = 0
        for name, email in EMPLOYERS:
            if await db.scalar(select(Employer.id).where(Employer.email == email)):
                continue
            employer = Employer(company_name=name, email=email, password_hash=password_hash, email_verified_at=now)
            db.add(employer)
            await db.flush()
            _consents(db, "employer", employer.id, now)
            employers += 1
        created = 0
        for fsp_id in ["FSP001", "FSP002", *[f"FSP{n}" for n in range(1000, 1150)]]:
            if await db.scalar(select(Participant.id).where(Participant.fsp_id == fsp_id)):
                continue
            data = await adapter.fetch_participant(fsp_id)
            if data is None:
                continue
            participant = await ingest_from_fsp(db, data)
            rng = random.Random(fsp_id)
            if fsp_id in DEMOS:
                names, years = DEMOS[fsp_id]
                participant.experience_years = years
                participant.public_profile = not participant.is_minor
            else:
                disc = data.results[0].discipline if data.results else "algorithmic"
                pool = SKILLS[disc]
                names = rng.sample(pool, k=rng.randint(3, len(pool)))
                if rng.random() < 0.85:
                    participant.experience_years = rng.randint(0, 12)
                participant.public_profile = (not participant.is_minor) and rng.random() < 0.30
            for name in names:
                db.add(Skill(participant_id=participant.id, name=name, raw_name=name,
                             trust_level="self_reported", confirmed=True))
            participant.email = f"{fsp_id.lower()}@demo.talent"
            participant.email_verified_at = now
            # Survey answers: the demo accounts have them; synthetic profiles get the role of their discipline.
            first = data.results[0].discipline if data.results else "algorithmic"
            participant.specialization = SPEC_OF.get(fsp_id) or DISCIPLINE_ROLE_MAP.get(first, "backend")
            participant.industry = rng.choice(list(INDUSTRIES))
            participant.work_goal = "both" if participant.is_minor else rng.choice(["job", "job", "both", "internship"])
            participant.survey_at = now
            if fsp_id in DEMOS:
                participant.password_hash = password_hash
            _consents(db, "participant", participant.id, now)
            if participant.public_profile:
                doc = documents()["pd_distribution"]
                db.add(Consent(subject_type="participant", subject_id=participant.id, kind=doc.kind,
                               version=doc.version, sha256=doc.sha256, given_at=now))
            await rebuild_profile(db, participant)
            created += 1
            if created % 25 == 0:
                await db.commit()
        email, name, region, years, grade, skill_names = NO_FSP_DEMO
        if not await db.scalar(select(Participant.id).where(Participant.email == email)):
            # TZ 2.1: a candidate without FSP history is a normal case, not an error.
            participant = Participant(email=email, display_name=name, region=region, experience_years=years,
                                      declared_grade=grade, password_hash=password_hash, email_verified_at=now,
                                      is_minor=False, is_visible=True, public_profile=False,
                                      specialization="backend", industry="fintech", work_goal="job", survey_at=now)
            db.add(participant)
            await db.flush()
            for skill in skill_names:
                db.add(Skill(participant_id=participant.id, name=skill, raw_name=skill,
                             trust_level="self_reported", confirmed=True))
            _consents(db, "participant", participant.id, now)
            await rebuild_profile(db, participant)
            created += 1
        demo_jobs = [
            ("hr@sibcode.demo", "Backend-разработчик", "backend", "middle", "algorithmic", "I",
             ["Python", "FastAPI", "PostgreSQL"], 180000, 260000),
            ("hr@perimeter.demo", "Специалист по ИБ", "security", "middle", "security", "II",
             ["Python", "Linux", "Web Security"], 160000, 240000),
        ]
        jobs = 0
        for email, title, role, grade, disc, rank, skills, lo, hi in demo_jobs:
            employer = await db.scalar(select(Employer).where(Employer.email == email))
            if employer is None:
                continue
            exists = await db.scalar(
                select(Vacancy.id).where(Vacancy.employer_id == employer.id, Vacancy.title == title))
            if exists:
                continue
            db.add(Vacancy(employer_id=employer.id, title=title, role=role, grade=grade, discipline=disc,
                           min_rank=rank, skills=skills, salary_from_gross=lo, salary_to_gross=hi,
                           work_format="remote"))
            jobs += 1
        await db.commit()
        print(f"seeded employers={employers} participants={created} vacancies={jobs}")
    await seed_questions()
    # Completed tests, needs, invitations and applications, so the demo shows every step without setup.
    from seed.demo_activity import main as demo_activity
    await demo_activity()


if __name__ == "__main__":
    asyncio.run(main())
