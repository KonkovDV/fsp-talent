"""Idempotent demo data.

Logins (password demo12345): jury1..jury10@demo.talent (empty survey, full test without pauses under DEMO_MODE),
candidates fsp001@demo.talent, fsp002@demo.talent (FSP linked) and
nofsp@demo.talent (no FSP history); employer hr@sibcode.demo. Companies are fictional.
"""
import argparse
import asyncio
import os
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.legal import documents
from app.models import Consent, Employer, Participant, Skill, Vacancy
from app.services.categorization import DISCIPLINE_ROLE_MAP, grade_from_experience
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


def job_search_of(rng: random.Random) -> str:
    """40 % actively looking, 45 % open to offers, 15 % not looking."""
    return rng.choices(("active", "open", "not_looking"), weights=(40, 45, 15), k=1)[0]


# Load-test profiles. Not people: no phone, no messenger, no birth date, a fixed mailbox on load.talent.
EXTRA_SPECS = (
    ("backend", ["Python", "PostgreSQL", "FastAPI", "Docker"]),
    ("frontend", ["TypeScript", "React", "JavaScript", "HTML/CSS"]),
    ("fullstack", ["TypeScript", "React", "Python", "PostgreSQL"]),
    ("ml", ["Python", "PyTorch", "Pandas", "SQL"]),
    ("devops", ["Docker", "Kubernetes", "Linux", "Nginx"]),
    ("qa", ["Python", "Testing", "SQL", "Linux"]),
)
EXTRA_GRADES = ("intern", "junior", "middle", "senior", "lead")
EXTRA_REGIONS = ("Новосибирск", "Казань", "Екатеринбург", "Москва")


def extra_email(n: int) -> str:
    return f"extra{n:05d}@load.talent"


def extra_spec(n: int) -> dict:
    """Deterministic synthetic profile. The same n always yields the same skills and grade."""
    rng = random.Random(n)
    spec, pool = EXTRA_SPECS[(n - 1) % len(EXTRA_SPECS)]
    return {
        "email": extra_email(n),
        "display_name": f"Профиль {n:05d}",
        "specialization": spec,
        "declared_grade": EXTRA_GRADES[(n - 1) % len(EXTRA_GRADES)],
        "skills": rng.sample(pool, k=rng.randint(3, len(pool))),
        "experience_years": rng.randint(0, 12),
        "job_search": job_search_of(rng),
        "region": rng.choice(EXTRA_REGIONS),
        "industry": rng.choice(tuple(INDUSTRIES)),
    }


SHOWCASE_SPECS = ("backend", "frontend", "fullstack", "ml", "devops", "qa")
SHOWCASE_CORE = ("junior", "middle", "senior")
_SHOWCASE_SKILLS = {spec: skills for spec, skills in EXTRA_SPECS}


def showcase_adds(counts: dict[tuple[str, str], int]) -> list[tuple[str, str, int]]:
    """How many profiles each key cell still needs: six at junior/middle/senior, and one edge of five."""
    adds: list[tuple[str, str, int]] = []
    for spec in SHOWCASE_SPECS:
        for grade in SHOWCASE_CORE:
            missing = 6 - counts.get((spec, grade), 0)
            if missing > 0:
                adds.append((spec, grade, missing))
        if counts.get((spec, "intern"), 0) < 5 and counts.get((spec, "lead"), 0) < 5:
            adds.append((spec, "intern", 5 - counts.get((spec, "intern"), 0)))
    return adds


async def _sit_grade(db, person: Participant, grade: str) -> bool:
    """One real session, answered correctly, so the grade comes from the test."""
    from app.services import assessment
    session, item = await assessment.start_session(
        db, person.id, person.specialization, grade, code_language="python")
    for _ in range(25):
        token = assessment.item_token(session.id, item.seq, item.id)
        if item.typed:
            text = str(int(item.options[item.correct_index]))
            session, item, finished = await assessment.answer_item(
                db, session.id, person.id, token, answer_text=text)
        else:
            session, item, finished = await assessment.answer_item(
                db, session.id, person.id, token, item.correct_index)
        if finished is not None:
            break
    await db.refresh(person)
    return person.assessed_grade == grade


async def fill_showcase() -> None:
    """Fill the six key rows of the bank and confirm enough grades by test. Idempotent. Demo logins stay."""
    from app.core.rls import bypass_rls
    from app.models.profile import ProfileSearchIndex
    bypass_rls()
    async with AsyncSessionLocal() as db:
        password_hash = hash_password(DEMO_PASSWORD)
        now = datetime.now(UTC)
        visible = and_(
            Participant.is_visible.is_(True),
            Participant.job_search != "not_looking",
            Participant.is_minor.is_(False),
        )
        rows = (await db.execute(
            select(ProfileSearchIndex.role, ProfileSearchIndex.grade, func.count())
            .join(Participant, Participant.id == ProfileSearchIndex.participant_id)
            .where(visible)
            .group_by(ProfileSearchIndex.role, ProfileSearchIndex.grade))).all()
        counts = {(role, grade): n for role, grade, n in rows}
        created = 0
        for spec, grade, missing in showcase_adds(counts):
            have = await db.scalar(select(func.count()).select_from(Participant).where(
                Participant.email.like(f"showcase-{spec}-{grade}-%@demo.talent"))) or 0
            skills = _SHOWCASE_SKILLS[spec]
            for n in range(have + 1, have + 1 + missing):
                email = f"showcase-{spec}-{grade}-{n:02d}@demo.talent"
                fresh = n % 2 == 0
                person = Participant(
                    email=email, display_name=f"Профиль {spec} {grade} {n:02d}", region="Новосибирск",
                    experience_years=0 if grade == "intern" else 3, declared_grade=grade,
                    password_hash=password_hash, email_verified_at=now, is_minor=False, is_visible=True,
                    public_profile=False, specialization=spec, industry="fintech", work_goal="job",
                    survey_at=now, job_search="open",
                    created_at=now - timedelta(days=3 if fresh else 40))
                db.add(person)
                await db.flush()
                for name in skills:
                    db.add(Skill(participant_id=person.id, name=name, raw_name=name,
                                 trust_level="self_reported", confirmed=True))
                _consents(db, "participant", person.id, now)
                await rebuild_profile(db, person)
                created += 1
        await db.commit()
        targets = list(await db.scalars(select(Participant).where(
            Participant.email.like("showcase-%@demo.talent"), Participant.assessed_grade.is_(None))))
        spare_rows = (await db.execute(
            select(Participant, ProfileSearchIndex.role, ProfileSearchIndex.grade)
            .join(ProfileSearchIndex, ProfileSearchIndex.participant_id == Participant.id)
            .where(visible, Participant.assessed_grade.is_(None),
                   ProfileSearchIndex.role.is_not(None), ProfileSearchIndex.grade.is_not(None),
                   Participant.email.notin_(("fsp001@demo.talent", "fsp002@demo.talent", "nofsp@demo.talent")),
                   Participant.email.notlike("jury%@demo.talent"))
            .limit(25))).all()
        sat = passed = 0
        for person in targets:
            email = person.email
            if not person.specialization:
                continue
            grade = person.declared_grade if person.declared_grade in ("intern", *SHOWCASE_CORE, "lead") else "junior"
            try:
                ok = await _sit_grade(db, person, grade)
            except Exception as exc:
                await db.rollback()
                print(f"showcase test skipped {email}: {type(exc).__name__}")
                continue
            await db.commit()
            sat += 1
            passed += int(ok)
        for person, role, grade in spare_rows:
            email = person.email
            if person.specialization != role or person.declared_grade != grade:
                person.specialization = role
                person.declared_grade = grade
                await rebuild_profile(db, person)
            try:
                ok = await _sit_grade(db, person, grade)
            except Exception as exc:
                await db.rollback()
                print(f"showcase test skipped {email}: {type(exc).__name__}")
                continue
            await db.commit()
            sat += 1
            passed += int(ok)
            if sat % 10 == 0:
                print(f"showcase tests {sat}")
        in_search = await db.scalar(select(func.count()).select_from(Participant).where(visible)) or 0
        tested = await db.scalar(select(func.count()).select_from(Participant).where(
            visible, Participant.assessed_grade.is_not(None))) or 0
        cells = (await db.execute(
            select(func.count()).select_from(
                select(ProfileSearchIndex.role, ProfileSearchIndex.grade)
                .join(Participant, Participant.id == ProfileSearchIndex.participant_id)
                .where(visible)
                .group_by(ProfileSearchIndex.role, ProfileSearchIndex.grade)
                .having(func.count() >= 5)
                .subquery()))).scalar() or 0
        fresh = await db.scalar(select(func.count()).select_from(Participant).where(
            visible, Participant.created_at >= now - timedelta(days=14))) or 0
        share = tested / in_search if in_search else 0
        print(f"showcase created={created} tests={sat} passed={passed} "
              f"visible_cells={cells} in_search={in_search} tested={tested} "
              f"share={share:.2f} fresh_14d={fresh}")


async def sync_extra(n: int) -> None:
    """Keep exactly n synthetic profiles visible. n = 0 hides them. Demo accounts are not touched."""
    from app.core.rls import bypass_rls
    bypass_rls()
    if n < 0:
        raise SystemExit("--extra-candidates не бывает отрицательным")
    async with AsyncSessionLocal() as db:
        password_hash = hash_password(DEMO_PASSWORD)
        now = datetime.now(UTC)
        rows = list(await db.scalars(select(Participant).where(Participant.email.like("extra%@load.talent"))))
        by_email = {p.email: p for p in rows}
        wanted = {extra_email(i) for i in range(1, n + 1)}
        created = 0
        for i in range(1, n + 1):
            spec = extra_spec(i)
            participant = by_email.get(spec["email"])
            if participant is None:
                participant = Participant(
                    email=spec["email"], display_name=spec["display_name"], region=spec["region"],
                    experience_years=spec["experience_years"], declared_grade=spec["declared_grade"],
                    password_hash=password_hash, email_verified_at=now, is_minor=False, is_visible=True,
                    public_profile=False, specialization=spec["specialization"], industry=spec["industry"],
                    work_goal="job", survey_at=now, job_search=spec["job_search"])
                db.add(participant)
                await db.flush()
                for name in spec["skills"]:
                    db.add(Skill(participant_id=participant.id, name=name, raw_name=name,
                                 trust_level="self_reported", confirmed=True))
                _consents(db, "participant", participant.id, now)
                await rebuild_profile(db, participant)
                created += 1
                if created % 100 == 0:
                    await db.commit()
                    print(f"extra created {created}")
            else:
                participant.is_visible = True
                participant.job_search = spec["job_search"]
                participant.deleted_at = None
        for email, participant in by_email.items():
            if email not in wanted:
                participant.is_visible = False
                participant.job_search = "not_looking"
        await db.commit()
        visible = await db.scalar(select(func.count()).select_from(Participant).where(
            Participant.email.like("extra%@load.talent"), Participant.is_visible.is_(True),
            Participant.job_search != "not_looking"))
        print(f"extra participants={n} created={created} in_search={visible or 0}")


async def ensure_pay_wishes() -> None:
    """Name a few gross wishes so the demo need can show the pay hint.

    The hint appears only when at least five people named a number. Some wishes sit under the
    demo ceiling of 260 000, some just above it, so raising the ceiling covers more people.
    The show accounts and the load-test profiles are left as they are.
    """
    from app.core.rls import bypass_rls
    bypass_rls()
    floors = (220_000, 240_000, 280_000, 285_000, 290_000, 295_000)
    protected = ("fsp001@demo.talent", "fsp002@demo.talent", "nofsp@demo.talent")
    async with AsyncSessionLocal() as db:
        # The demo need asks for Python and PostgreSQL, so the wishes have to sit in that pool.
        from app.models.profile import ProfileSearchIndex
        in_demo_need = ProfileSearchIndex.skills_tsv.op("@@")(func.to_tsquery("simple", "Python & PostgreSQL"))
        people = list(await db.scalars(
            select(Participant).join(
                ProfileSearchIndex, ProfileSearchIndex.participant_id == Participant.id,
            ).where(
                Participant.is_visible.is_(True),
                Participant.job_search != "not_looking",
                Participant.salary_from_gross.is_(None),
                Participant.email.notin_(protected),
                Participant.email.notlike("jury%@demo.talent"),
                Participant.email.notlike("extra%@load.talent"),
                in_demo_need,
            ).limit(len(floors))))
        for person, floor in zip(people, floors):
            person.salary_from_gross = floor
            person.salary_to_gross = floor + 40_000
        await db.commit()
        print(f"pay wishes set={len(people)}")


async def ensure_category_market() -> None:
    """Name wishes in Backend · middle outside the demo search pool.

    The candidate cabinet shows quartiles only when five people named a sum. These profiles
    do not match the demo need's Python and PostgreSQL query, so that need's pay hint stays put.
    Show accounts and the load-test profiles are left as they are.
    """
    from app.core.rls import bypass_rls
    from app.models import CategoryAssignment
    from app.models.profile import ProfileSearchIndex
    bypass_rls()
    floors = (190_000, 230_000, 260_000, 300_000, 340_000, 380_000)
    protected = ("fsp001@demo.talent", "fsp002@demo.talent", "nofsp@demo.talent")
    in_demo_need = ProfileSearchIndex.skills_tsv.op("@@")(func.to_tsquery("simple", "Python & PostgreSQL"))
    async with AsyncSessionLocal() as db:
        people = list(await db.scalars(
            select(Participant)
            .join(CategoryAssignment, CategoryAssignment.participant_id == Participant.id)
            .outerjoin(ProfileSearchIndex, ProfileSearchIndex.participant_id == Participant.id)
            .where(
                CategoryAssignment.primary_role == "backend",
                CategoryAssignment.grade == "middle",
                Participant.is_visible.is_(True),
                Participant.salary_from_gross.is_(None),
                Participant.email.notin_(protected),
                Participant.email.notlike("jury%@demo.talent"),
                Participant.email.notlike("extra%@load.talent"),
                or_(ProfileSearchIndex.participant_id.is_(None), ~in_demo_need),
            )
            .order_by(Participant.email)
            .limit(len(floors))))
        for person, floor in zip(people, floors):
            person.salary_from_gross = floor
            person.salary_to_gross = floor + 40_000
        await db.commit()
        print(f"category market set={len(people)}")


async def main(extra_candidates: int | None = None) -> None:
    _refuse_production()
    from app.core.rls import bypass_rls
    bypass_rls()
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
                participant.job_search = "open"
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
                participant.job_search = job_search_of(rng)
            for name in names:
                db.add(Skill(participant_id=participant.id, name=name, raw_name=name,
                             trust_level="self_reported", confirmed=True))
            # The survey grade is the candidate's own choice; demo people choose what their experience suggests.
            years_told = participant.experience_years
            participant.declared_grade = participant.declared_grade or grade_from_experience(years_told)
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
        # Jury accounts: empty survey, so a jury member walks the candidate path from step one.
        # With DEMO_MODE they take the full test without pauses (app.services.assessment.jury_unlimited).
        for n in range(1, 11):
            email = f"jury{n}@demo.talent"
            if await db.scalar(select(Participant.id).where(Participant.email == email)) is not None:
                continue
            juror = Participant(email=email, display_name=f"Член жюри {n}", password_hash=password_hash,
                                email_verified_at=now, is_minor=False, is_visible=True, public_profile=False)
            db.add(juror)
            await db.flush()
            _consents(db, "participant", juror.id, now)
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
    await fill_showcase()
    await ensure_pay_wishes()
    await ensure_category_market()
    if extra_candidates is not None:
        await sync_extra(extra_candidates)


def _refuse_production() -> None:
    if os.environ.get("ENV", "").lower() == "production":
        raise SystemExit("Демо-данные не загружаются, когда ENV=production")


if __name__ == "__main__":
    _refuse_production()
    parser = argparse.ArgumentParser()
    parser.add_argument("--extra-candidates", type=int, default=None,
                        help="сколько синтетических профилей держать в поиске; 0 прячет их")
    args = parser.parse_args()
    asyncio.run(main(extra_candidates=args.extra_candidates))
