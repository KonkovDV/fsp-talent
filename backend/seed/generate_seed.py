"""Idempotent demo data.

Logins (password demo12345): candidates fsp001@demo.talent, fsp002@demo.talent (FSP linked) and
nofsp@demo.talent (no FSP history); employer hr@sibcode.demo. Companies are fictional.
"""
import asyncio
import os
import random
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.legal import documents
from app.models import Consent, Employer, Participant, Skill, Vacancy
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
# Survey answer of a synthetic participant: competitors of one discipline go to different jobs.
# Without this every algorithmic athlete would be "backend" and an ML need would find nobody of its own.
SPEC_CHOICE = {
    "algorithmic": (("backend", "ml", "fullstack", "devops", "data"), (42, 28, 12, 8, 10)),
    "product": (("fullstack", "frontend", "backend", "mobile"), (40, 35, 15, 10)),
    "security": (("security", "devops"), (80, 20)),
    "bas": (("embedded",), (1,)),
    "robotics": (("embedded", "ml"), (75, 25)),
}
SKILLS_OF_SPEC = {
    "ml": ["Python", "PyTorch", "Pandas", "NumPy", "scikit-learn", "SQL", "NLP"],
    "frontend": ["TypeScript", "React", "JavaScript", "HTML/CSS", "Next.js"],
    "mobile": ["Kotlin", "TypeScript", "React", "Algorithms"],
    "devops": ["Docker", "Kubernetes", "Linux", "Nginx", "Python"],
    "data": ["Python", "SQL", "PostgreSQL", "Airflow", "Spark", "Kafka"],
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


# Vacancies of the fictional companies. The text matters: the test for a vacancy takes its topics from the
# skills named here and quotes the sentence it found them in (app/services/vacancy_exam.py).
DEMO_VACANCIES = [
    ("hr@sibcode.demo", "Backend-разработчик", "backend", "middle", "algorithmic", "I",
     ["Python", "FastAPI", "PostgreSQL"], 180000, 260000, "remote",
     "Платёжный сервис для малого бизнеса. Пишем API на Python и FastAPI, данные храним в PostgreSQL, "
     "очереди на Redis. Нужен человек, который сам доведёт задачу от схемы БД до релиза и разберётся "
     "в медленном SQL-запросе."),
    ("hr@sibcode.demo", "Стажёр backend", "backend", "intern", None, None,
     ["Python", "SQL", "Algorithms"], 60000, 90000, "hybrid",
     "Стажировка на три месяца с наставником. Нужны уверенный Python, основы SQL и алгоритмы на уровне "
     "школьной олимпиады. Подойдёт студентам и участникам соревнований ФСП."),
    ("hr@perimeter.demo", "Специалист по ИБ", "security", "middle", "security", "II",
     ["Python", "Linux", "Web Security"], 160000, 240000, "remote",
     "Центр мониторинга безопасности. Проводим пентест веб-приложений клиентов, пишем отчёты и "
     "автоматизацию на Python. Нужны Linux, Web Security и опыт CTF."),
    ("hr@perimeter.demo", "Аналитик SOC", "security", "junior", "security", None,
     ["Linux", "Networking", "Forensics"], 110000, 150000, "office",
     "Первая линия SOC: разбор инцидентов, корреляция событий, сетевой трафик. Нужны Linux, понимание "
     "сетей (Networking) и интерес к Forensics. Обучаем внутри команды."),
    ("hr@quantumlab.demo", "ML-инженер (NLP)", "ml", "middle", "algorithmic", None,
     ["Python", "PyTorch", "NLP", "SQL"], 230000, 320000, "remote",
     "Рекомендательные системы для ритейла. Обучаем модели на PyTorch, работаем с NLP и LLM, данные "
     "готовим на SQL и Pandas. Нужен опыт доведения модели до продакшна."),
    ("hr@quantumlab.demo", "Frontend-разработчик", "frontend", "junior", "product", None,
     ["TypeScript", "React", "HTML/CSS"], 120000, 170000, "hybrid",
     "Интерфейсы для аналитиков: дашборды и редакторы правил. Стек: TypeScript, React, HTML/CSS. "
     "Ценим аккуратную вёрстку и понимание того, как работает браузер."),
    ("hr@cloudwhale.demo", "DevOps-инженер", "devops", "middle", None, None,
     ["Docker", "Kubernetes", "Linux", "Nginx"], 200000, 280000, "remote",
     "Облачная платформа в трёх дата-центрах. Поддерживаем Kubernetes, собираем Docker-образы, "
     "настраиваем Nginx и сети на Linux. Дежурства раз в шесть недель."),
    ("hr@cloudwhale.demo", "Go-разработчик", "backend", "senior", "algorithmic", None,
     ["Go", "PostgreSQL", "Kubernetes", "Algorithms"], 300000, 400000, "remote",
     "Пишем на Go контроллеры объектного хранилища. Нужны сильные алгоритмы, PostgreSQL и опыт "
     "работы с Kubernetes. Решения о дизайне принимает команда, без согласований сверху."),
    ("hr@robotech.demo", "Инженер встраиваемых систем", "embedded", "junior", "robotics", None,
     ["C++", "STM32", "RTOS", "ROS"], 120000, 170000, "office",
     "Прошивки для промышленных роботов и беспилотников. Пишем на C++ под STM32 с RTOS, верхний уровень "
     "на ROS. Подойдёт участникам соревнований ФСП по робототехнике и БАС."),
]


async def main() -> None:
    _refuse_production()
    adapter = MockFSPAdapter()
    async with AsyncSessionLocal() as db:
        password_hash = hash_password(DEMO_PASSWORD)
        now = datetime.now(UTC)
        employers = 0
        for name, email in EMPLOYERS:
            existing = await db.scalar(select(Employer).where(Employer.email == email))
            if existing is not None:
                if not existing.password_hash:
                    existing.password_hash = password_hash
                    existing.email_verified_at = existing.email_verified_at or now
                continue
            employer = Employer(company_name=name, email=email, password_hash=password_hash, email_verified_at=now)
            db.add(employer)
            await db.flush()
            _consents(db, "employer", employer.id, now)
            employers += 1
        created = 0
        for fsp_id in ["FSP001", "FSP002", *[f"FSP{n}" for n in range(1000, 1150)]]:
            existing = await db.scalar(select(Participant).where(Participant.fsp_id == fsp_id))
            if existing is not None:
                if fsp_id in DEMOS and not existing.password_hash:
                    existing.password_hash = password_hash
                    existing.email_verified_at = existing.email_verified_at or now
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
                options, weights = SPEC_CHOICE.get(disc, (("backend",), (1,)))
                spec = rng.choices(options, weights=weights)[0]
                pool = SKILLS_OF_SPEC.get(spec, SKILLS[disc])
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
            participant.specialization = (SPEC_OF.get(fsp_id) or (spec if fsp_id not in DEMOS else None)
                                          or DISCIPLINE_ROLE_MAP.get(first, "backend"))
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
        existing_plain = await db.scalar(select(Participant).where(Participant.email == email))
        if existing_plain is not None:
            if not existing_plain.password_hash:
                existing_plain.password_hash = password_hash
                existing_plain.email_verified_at = existing_plain.email_verified_at or now
        else:
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
        jobs = 0
        for email, title, role, grade, disc, rank, skills, lo, hi, fmt, text in DEMO_VACANCIES:
            employer = await db.scalar(select(Employer).where(Employer.email == email))
            if employer is None:
                continue
            existing = await db.scalar(
                select(Vacancy).where(Vacancy.employer_id == employer.id, Vacancy.title == title))
            if existing is not None:
                existing.description = existing.description or text
                continue
            db.add(Vacancy(employer_id=employer.id, title=title, description=text, role=role, grade=grade,
                           discipline=disc, min_rank=rank, skills=skills, salary_from_gross=lo,
                           salary_to_gross=hi, work_format=fmt))
            jobs += 1
        await db.commit()
        print(f"seeded employers={employers} participants={created} vacancies={jobs}")
    # Completed tests, needs, invitations and applications, so the demo shows every step without setup.
    from seed.demo_activity import main as demo_activity
    await demo_activity()


def _refuse_production() -> None:
    if os.environ.get("ENV", "").lower() == "production":
        raise SystemExit("Демо-данные не загружаются, когда ENV=production")


if __name__ == "__main__":
    _refuse_production()
    asyncio.run(main())
