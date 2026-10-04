"""Idempotent demo data. Participants: FSP001 / test. Employer: hr@yandex.demo / demo12345."""
import asyncio
import random

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import Employer, Participant, Skill, Vacancy
from app.services.fsp.mock import MockFSPAdapter
from app.services.profile import ingest_from_fsp, rebuild_profile

SKILLS = {
    "algorithmic": ["Python", "C++", "Algorithms", "Go", "Rust"],
    "product": ["TypeScript", "React", "Node.js", "PostgreSQL", "Docker"],
    "security": ["Pentesting", "CTF", "Linux", "Web Security", "Python"],
    "bas": ["C++", "Python", "PX4/ArduPilot", "ROS", "STM32"],
    "robotics": ["C++", "ROS", "Python", "Arduino", "Computer Vision"],
}
EMPLOYERS = [
    ("Яндекс", "hr@yandex.demo"), ("Сбер", "hr@sber.demo"), ("Т-Банк", "hr@tbank.demo"),
    ("VK", "hr@vk.demo"), ("Авиасейлс", "hr@aviasales.demo"),
]
DEMOS = {
    "FSP001": (["Python", "Go", "FastAPI", "PostgreSQL", "Algorithms", "Docker"], 3),
    "FSP002": (["Pentesting", "CTF", "Linux", "Web Security", "Python"], 4),
}


async def main() -> None:
    adapter = MockFSPAdapter()
    async with AsyncSessionLocal() as db:
        password_hash = hash_password("demo12345")
        employers = 0
        for name, email in EMPLOYERS:
            if await db.scalar(select(Employer.id).where(Employer.email == email)):
                continue
            db.add(Employer(company_name=name, email=email, password_hash=password_hash))
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
            await rebuild_profile(db, participant)
            created += 1
            if created % 25 == 0:
                await db.commit()
        demo_jobs = [
            ("hr@yandex.demo", "Backend-разработчик", "backend", "middle", "algorithmic", "I",
             ["Python", "FastAPI", "PostgreSQL"], 180000, 260000),
            ("hr@sber.demo", "Специалист по ИБ", "security", "middle", "security", "II",
             ["Python", "Linux", "Web Security"], 160000, 240000),
        ]
        jobs = 0
        for email, title, role, grade, disc, rank, skills, lo, hi in demo_jobs:
            employer = await db.scalar(select(Employer).where(Employer.email == email))
            if employer is None:
                continue
            exists = await db.scalar(select(Vacancy.id).where(Vacancy.employer_id == employer.id, Vacancy.title == title))
            if exists:
                continue
            db.add(Vacancy(employer_id=employer.id, title=title, role=role, grade=grade, discipline=disc,
                           min_rank=rank, skills=skills, salary_from_gross=lo, salary_to_gross=hi,
                           work_format="remote"))
            jobs += 1
        await db.commit()
        print(f"seeded employers={employers} participants={created} vacancies={jobs}")


if __name__ == "__main__":
    asyncio.run(main())
