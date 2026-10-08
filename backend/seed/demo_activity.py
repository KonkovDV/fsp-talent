"""Demo activity on top of the base seed, so every screen shows the mechanics without a live walk-through.

- 40 fictional candidates take the adaptive grade test through the same service the API uses
  (start_session -> answer_item -> finalize). Answers are simulated from an ability drawn per candidate with
  the 3PL model of each served item, so confirmed grades, item statistics and topic results are real outputs.
- The demo employer «Сибирский код» gets three needs with shortlists; employers send invitations in every
  status; candidates apply to vacancies; notifications are written for each step (no letters are sent).
- «Сибирский код» also writes three tasks: a public one with a numeric reference, a public open one with an
  answer waiting for its review, and one addressed to fsp001@demo.talent.

Deterministic (fixed seeds) and idempotent: it does nothing if the demo needs already exist.
Demo accounts used by the smoke test (FSP001, FSP002, nofsp, offers from hr@sibcode.demo to FSP001) are left
for the smoke test to exercise.
"""
from __future__ import annotations

import asyncio
import math
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.api.v1.needs import NeedParams
from app.core.database import AsyncSessionLocal
from app.models import (
    Application,
    CategoryAssignment,
    Employer,
    EmployerTask,
    Need,
    NeedShortlist,
    NeedVersion,
    Offer,
    Participant,
    TaskSubmission,
    Vacancy,
)
from app.services import assessment
from app.services.notify import Outbox, category_label, notify, salary
from app.services.practice import offer_weekly_tasks
from app.services.profile import rebuild_profile
from app.services.search.pipeline import search_candidates
from app.services.tasks import check_answer, record_verdict

GRADES = ("junior", "middle", "senior", "lead")
THETA_CENTER = {"junior": -0.6, "middle": 0.4, "senior": 1.4, "lead": 2.3}
SKIP = {"FSP001", "FSP002"}
DEMO_EMPLOYER = "hr@sibcode.demo"

NEEDS = [
    ("Backend на Python в платёжный сервис",
     {"role": "backend", "grade": "middle", "skills": ["Python", "PostgreSQL"], "nice_to_have": ["Docker", "Kafka"],
      "salary_from": 180000, "salary_to": 260000}),
    ("Аналитик SOC, первая линия",
     {"role": "security", "grade": "junior", "skills": ["Linux", "Web Security"], "nice_to_have": ["CTF"],
      "work_goal": "job"}),
    ("ML-инженер в команду рекомендаций",
     {"role": "ml", "grade": "middle", "skills": ["Python", "PyTorch"], "nice_to_have": ["SQL"]}),
]

# Pending invitations for the demo candidate accounts: fsp id, employer, role, salary, days ago
DEMO_INVITES = [
    ("FSP001", "hr@quantumlab.demo", "Backend-разработчик в ML-платформу", (230000, 300000), 1),
    ("FSP001", "hr@cloudwhale.demo", "Go-разработчик", (210000, 270000), 3),
    ("FSP002", "hr@perimeter.demo", "Аналитик SOC", (140000, 190000), 2),
]

# employer email, role text, salary, status, days ago
OFFERS = [
    ("hr@quantumlab.demo", "ML-инженер", (200000, 280000), "pending", 1),
    ("hr@cloudwhale.demo", "DevOps-инженер", (190000, 250000), "pending", 2),
    (DEMO_EMPLOYER, "Backend-разработчик", (180000, 240000), "accepted", 6),
    (DEMO_EMPLOYER, "Backend-разработчик", (170000, 230000), "rejected", 8),
    ("hr@perimeter.demo", "Специалист по ИБ", (150000, 210000), "accepted", 4),
    ("hr@robotech.demo", "Инженер встраиваемых систем", (160000, 220000), "withdrawn", 9),
    ("hr@quantumlab.demo", "Data scientist", (180000, 240000), "expired", 20),
    (DEMO_EMPLOYER, "Backend-разработчик (стажировка)", (60000, 90000), "pending", 0),
]


def _p_right(theta: float, a: float, b: float, c: float) -> float:
    return c + (1 - c) / (1 + math.exp(-1.7 * a * (theta - b)))


async def _simulate_tests(db, now: datetime) -> int:
    rows = list(await db.scalars(
        select(Participant).where(Participant.fsp_id.like("FSP1%"), Participant.specialization.is_not(None),
                                  Participant.is_minor.is_(False)).order_by(Participant.fsp_id)))
    done = 0
    for p in rows:
        if done >= 40 or p.fsp_id in SKIP:
            break
        if p.minor_now():
            continue
        rng = random.Random(f"demo-test:{p.fsp_id}")
        cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == p.id))
        target = next((g for g in (p.declared_grade, cat.grade if cat else None) if g in GRADES), None)
        target = target or rng.choices(GRADES, weights=(35, 40, 20, 5))[0]
        theta = rng.gauss(THETA_CENTER[target], 0.7)
        lang = rng.choice(["python", "python", "javascript", "go", "java", "kotlin", "csharp"])
        session, item = await assessment.start_session(db, p.id, p.specialization, target, code_language=lang)
        for _ in range(25):
            # Answer 30-90 s after the item was served, like a person reading the code.
            item.served_at = datetime.now(UTC) - timedelta(seconds=rng.randint(30, 90))
            await db.flush()
            right = rng.random() < _p_right(theta, item.a, item.b, item.c)
            token = assessment.item_token(session.id, item.seq, item.id)
            if item.typed:
                value = int(item.options[item.correct_index])
                text = str(value if right else value + rng.choice([-2, -1, 1, 2]))
                session, item, finished = await assessment.answer_item(db, session.id, p.id, token, answer_text=text)
            else:
                wrong = [i for i in range(len(item.options)) if i != item.correct_index]
                choice = item.correct_index if right else rng.choice(wrong)
                session, item, finished = await assessment.answer_item(db, session.id, p.id, token, choice)
            if finished is not None:
                break
        # Spread the finish dates over the last month.
        session.completed_at = now - timedelta(days=rng.randint(1, 30), hours=rng.randint(0, 23))
        await rebuild_profile(db, p)
        await db.commit()
        done += 1
    return done


async def _needs(db, employer: Employer, now: datetime) -> int:
    for i, (title, params) in enumerate(NEEDS):
        p = NeedParams(**params)
        # The first need is the newest, so it opens first in the cabinet: the README scenario starts there.
        need = Need(employer_id=employer.id, title=title, version=1, created_at=now - timedelta(days=3 + i),
                    updated_at=now - timedelta(days=3 + i))
        db.add(need)
        await db.flush()
        db.add(NeedVersion(need_id=need.id, version=1, params=p.model_dump(), created_at=need.created_at))
        found = await search_candidates(db, skills=p.skills, q=p.q, limit=10, has_fsp=p.has_fsp,
                                        work_goal=p.work_goal, need=p.spec())
        for rank, card in enumerate(found["items"][:3]):
            db.add(NeedShortlist(need_id=need.id, participant_id=card["candidate_id"], version=1,
                                 score=(card.get("match") or {}).get("score"),
                                 status="invited" if rank == 0 else "shortlisted",
                                 added_at=now - timedelta(days=2 + i, hours=rank)))
    await db.flush()
    return len(NEEDS)


async def _offers(db, now: datetime) -> int:
    employers = {e.email: e for e in await db.scalars(select(Employer))}
    pool = list(await db.scalars(
        select(Participant).join(CategoryAssignment, CategoryAssignment.participant_id == Participant.id)
        .where(Participant.fsp_id.like("FSP1%"), Participant.is_visible.is_(True), Participant.is_minor.is_(False),
               Participant.assessed_grade.is_not(None))
        .order_by(Participant.fsp_id)))
    outbox = Outbox()
    made = 0
    for k, (email, role, (lo, hi), status, days) in enumerate(OFFERS):
        employer = employers.get(email)
        if employer is None or k >= len(pool):
            continue
        cand = pool[k * 3 % len(pool)]
        created = now - timedelta(days=days, hours=2)
        offer = Offer(employer_id=employer.id, candidate_id=cand.id, salary_from_gross=lo, salary_to_gross=hi,
                      role=role, work_format="remote" if k % 2 else "hybrid", contact_method=email,
                      message="Посмотрели ваш результат теста и протоколы ФСП. Будем рады познакомиться.",
                      status=status, created_at=created,
                      expires_at=created + timedelta(days=14))
        if status != "pending":
            offer.candidate_viewed_at = created + timedelta(hours=3)
        if status == "accepted":
            offer.contacts_revealed_at = created + timedelta(hours=5)
        db.add(offer)
        await db.flush()
        await notify(db, outbox, "participant", cand.id, "offer_new", f"Приглашение от «{employer.company_name}»",
                     f"{employer.company_name} приглашает на роль «{role}»: {salary(lo, hi)}.", "/candidate/offers")
        if status in ("accepted", "rejected"):
            cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == cand.id))
            who = category_label(cat.primary_role if cat else None, cat.grade if cat else None)
            verb = "принял" if status == "accepted" else "отклонил"
            await notify(db, outbox, "employer", employer.id, f"offer_{status}",
                         f"Кандидат {verb} приглашение «{role}»", f"Кандидат ({who}) {verb} приглашение.",
                         "/employer/offers")
        made += 1
    # The demo candidates open their cabinet to a real invitation. Not from hr@sibcode.demo: the smoke test
    # sends that one itself and expects no pending offer between the two.
    for fsp_id, email, role, (lo, hi), days in DEMO_INVITES:
        cand = await db.scalar(select(Participant).where(Participant.fsp_id == fsp_id))
        employer = employers.get(email)
        if cand is None or employer is None:
            continue
        created = now - timedelta(days=days, hours=3)
        db.add(Offer(employer_id=employer.id, candidate_id=cand.id, salary_from_gross=lo, salary_to_gross=hi,
                     role=role, work_format="hybrid", contact_method=email,
                     message="Видели ваш протокол ФСП. Расскажем о команде на коротком созвоне.",
                     status="pending", created_at=created, expires_at=created + timedelta(days=14)))
        await notify(db, outbox, "participant", cand.id, "offer_new", f"Приглашение от «{employer.company_name}»",
                     f"{employer.company_name} приглашает на роль «{role}»: {salary(lo, hi)}.", "/candidate/offers")
        made += 1
    outbox.letters.clear()   # seed writes the bell, it does not mail fictional addresses
    return made


async def restore_pending_invites(db) -> int:
    """Put the seed invitations for the show accounts back to «ожидает».

    An accepted or declined row is reopened. A missing row is created once.
    """
    employers = {e.email: e for e in await db.scalars(select(Employer))}
    restored = 0
    for fsp_id, email, role, (lo, hi), days in DEMO_INVITES:
        cand = await db.scalar(select(Participant).where(Participant.fsp_id == fsp_id))
        employer = employers.get(email)
        if cand is None or employer is None:
            continue
        offer = await db.scalar(select(Offer).where(
            Offer.employer_id == employer.id, Offer.candidate_id == cand.id, Offer.role == role))
        if offer is None:
            created = datetime.now(UTC) - timedelta(days=days, hours=3)
            db.add(Offer(employer_id=employer.id, candidate_id=cand.id, salary_from_gross=lo,
                         salary_to_gross=hi, role=role, work_format="hybrid", contact_method=email,
                         message="Видели ваш протокол ФСП. Расскажем о команде на коротком созвоне.",
                         status="pending", created_at=created, expires_at=created + timedelta(days=14)))
        else:
            offer.status = "pending"
            offer.contacts_revealed_at = None
            offer.contacts_revoked_at = None
            offer.responded_at = None
            offer.decline_reason = None
        restored += 1
    return restored


async def _applications(db, now: datetime) -> int:
    vacancies = list(await db.scalars(select(Vacancy).where(Vacancy.is_open.is_(True)).order_by(Vacancy.title)))
    outbox = Outbox()
    made = 0
    statuses = ["applied", "reviewing", "invited", "rejected", "applied", "reviewing"]
    for vacancy in vacancies:
        cands = list(await db.scalars(
            select(Participant).join(CategoryAssignment, CategoryAssignment.participant_id == Participant.id)
            .where(CategoryAssignment.primary_role == vacancy.role, Participant.fsp_id.like("FSP1%"),
                   Participant.is_visible.is_(True), Participant.is_minor.is_(False))
            .order_by(Participant.fsp_id).limit(2)))
        for cand in cands:
            status = statuses[made % len(statuses)]
            created = now - timedelta(days=3 - made % 3, hours=made)
            db.add(Application(vacancy_id=vacancy.id, candidate_id=cand.id, status=status, created_at=created,
                               viewed_at=None if status == "applied" else created + timedelta(hours=6)))
            await notify(db, outbox, "employer", vacancy.employer_id, "application_new",
                         f"Новый отклик на «{vacancy.title}»", "Откликнулся кандидат из вашей категории.",
                         "/employer/vacancies")
            made += 1
    outbox.letters.clear()
    return made


# Fictional companies: profile text the candidate reads in an invitation. No tax ids: a checksum-valid
# number could belong to a real company.
COMPANY_PROFILES = {
    "hr@sibcode.demo": ("Финтех", "sibcode.demo", "Платёжный сервис для малого бизнеса. Команда из 40 инженеров "
                        "в Новосибирске и удалённо, Python и Go, релизы каждый день."),
    "hr@quantumlab.demo": ("ИИ и данные", "quantumlab.demo", "Рекомендательные системы для ритейла. "
                           "Свой ML-стек, GPU-кластер, публикации на конференциях."),
    "hr@perimeter.demo": ("Информационная безопасность", "perimeter.demo", "Центр мониторинга безопасности (SOC) "
                          "24/7 для банков и госсектора, своя команда CTF."),
    "hr@cloudwhale.demo": ("Облачная инфраструктура", "cloudwhale.demo", "Облачная платформа с Kubernetes "
                           "и объектным хранилищем, дата-центры в трёх регионах."),
    "hr@robotech.demo": ("Робототехника", "robotech.demo", "Промышленные роботы и беспилотники, "
                         "встраиваемое ПО на C++ и ROS, производство в Екатеринбурге."),
}


async def _company_profiles(db) -> None:
    for email, (industry, site, about) in COMPANY_PROFILES.items():
        employer = await db.scalar(select(Employer).where(Employer.email == email))
        if employer is not None and not employer.description:
            employer.industry, employer.website, employer.description = industry, site, about


# title, statement, answer type, options, right option, reference number, audience
DEMO_TASKS = [
    ("Сколько строк вернёт JOIN",
     "В таблице orders 1000 строк, у 250 из них status = 'paid'. У каждого оплаченного заказа ровно две строки "
     "в order_items, у остальных строк в order_items нет.\n\nСколько строк вернёт запрос\n"
     "SELECT o.id FROM orders o JOIN order_items i ON i.order_id = o.id WHERE o.status = 'paid'?",
     "number", [], None, "500", "public"),
    ("Платёж списался дважды",
     "Клиент дважды нажал «Оплатить», и деньги списались два раза. Опишите, как сделать API платежей "
     "идемпотентным: что хранить, где проверять повтор и что вернуть клиенту на повторный запрос. "
     "Достаточно подхода, код не обязателен.",
     "open", [], None, None, "public"),
    ("Индекс для выборки заказов",
     "Запрос SELECT * FROM orders WHERE customer_id = $1 AND created_at >= $2 ORDER BY created_at DESC LIMIT 20 "
     "выполняется 2 секунды на 30 млн строк. Какой индекс ускорит его сильнее всего?",
     "choice", ["(created_at)", "(customer_id, created_at)", "(created_at, customer_id)", "(status)"], 1, None,
     "addressed"),
]
OPEN_ANSWERS = [
    "Клиент передаёт ключ идемпотентности в заголовке. Сервер в одной транзакции вставляет ключ в таблицу "
    "с уникальным индексом и создаёт платёж; повтор с тем же ключом получает сохранённый ответ, а не новый "
    "платёж. Ключи храню сутки, а на время обработки ставлю статус in_progress, чтобы параллельный повтор "
    "получил 409.",
    "Проверять в базе, был ли такой же платёж за последнюю минуту с той же суммой, и не проводить второй.",
]


async def _employer_tasks(db, now: datetime) -> int:
    """Three tasks of «Сибирский код» and a few answers. Idempotent: does nothing if the first task exists."""
    employer = await db.scalar(select(Employer).where(Employer.email == DEMO_EMPLOYER))
    if employer is None or await db.scalar(select(EmployerTask.id).where(
            EmployerTask.employer_id == employer.id, EmployerTask.title == DEMO_TASKS[0][0])):
        return 0
    demo = await db.scalar(select(Participant).where(Participant.email == "fsp001@demo.talent"))
    vacancy = await db.scalar(select(Vacancy).where(Vacancy.employer_id == employer.id, Vacancy.role == "backend")
                              .order_by(Vacancy.title).limit(1))
    outbox = Outbox()
    tasks = []
    for k, (title, text, kind, options, right, number, audience) in enumerate(DEMO_TASKS):
        if audience == "addressed" and demo is None:
            continue
        task = EmployerTask(
            employer_id=employer.id, vacancy_id=vacancy.id if vacancy else None, title=title, statement=text,
            answer_type=kind, options=options, correct_index=right, reference_number=number,
            visibility=audience, specialization="backend",
            candidate_id=demo.id if audience == "addressed" else None,
            deadline=now + timedelta(days=14), created_at=now - timedelta(days=3 - k))
        db.add(task)
        tasks.append(task)
        await db.flush()
        if audience == "addressed":
            await notify(db, outbox, "participant", demo.id, "task_new", f"Задание от «{employer.company_name}»",
                         f"Компания предлагает вам задание «{title}». Ответ проверит система. Грейд оно не меняет, "
                         "а результат появится в вашей карточке для работодателей.",
                         f"/candidate/tasks?task={task.id}")
    # Backend candidates of the synthetic pool answer the public tasks.
    pool = list(await db.scalars(
        select(Participant).where(Participant.fsp_id.like("FSP1%"), Participant.specialization == "backend",
                                  Participant.is_visible.is_(True), Participant.is_minor.is_(False))
        .order_by(Participant.fsp_id).limit(4)))
    number_task, open_task = tasks[0], tasks[1]
    made = 0
    for k, (person, answer) in enumerate(zip(pool[:3], ("500", "1000", "500"), strict=False)):
        checked = check_answer(number_task, answer, None)
        at = now - timedelta(days=2 - k, hours=k)
        db.add(TaskSubmission(task_id=number_task.id, participant_id=person.id, answer_text=checked.answer_text,
                              status="checked", passed=checked.passed, submitted_at=at, reviewed_at=at))
        record_verdict(person, number_task, checked.passed, at)
        made += 1
    if len(pool) >= 2:
        reviewed_at = now - timedelta(days=1)
        db.add(TaskSubmission(task_id=open_task.id, participant_id=pool[0].id, answer_text=OPEN_ANSWERS[0],
                              status="reviewed", passed=True, comment="Хороший подход: ключ и уникальный индекс.",
                              submitted_at=reviewed_at - timedelta(hours=5), reviewed_at=reviewed_at))
        record_verdict(pool[0], open_task, True, reviewed_at)
        # Waits for hr@sibcode.demo to review it in the demo.
        db.add(TaskSubmission(task_id=open_task.id, participant_id=pool[1].id, answer_text=OPEN_ANSWERS[1],
                              status="review", submitted_at=now - timedelta(hours=6)))
        await notify(db, outbox, "employer", employer.id, "task_submission",
                     f"Новый ответ на задание «{open_task.title}»",
                     "Кандидат прислал решение. Оно ждёт вашей проверки: зачтено или нет и короткий комментарий.",
                     f"/employer/tasks?task={open_task.id}")
        made += 2
    await db.flush()
    outbox.letters.clear()   # seed writes the bell, it does not mail fictional addresses
    return made


async def main() -> None:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        employer = await db.scalar(select(Employer).where(Employer.email == DEMO_EMPLOYER))
        if employer is None:
            print("demo activity: run seed.generate_seed first")
            return
        answers = await _employer_tasks(db, now)
        if answers:
            await db.commit()
            print(f"demo activity: employer task answers={answers}")
        if await db.scalar(select(Need.id).where(Need.employer_id == employer.id, Need.title == NEEDS[0][0])):
            print("demo activity: already seeded")
            return
        await _company_profiles(db)
        tests = await _simulate_tests(db, now)
        needs = await _needs(db, employer, now)
        offers = await _offers(db, now)
        apps = await _applications(db, now)
        weekly, outbox = await offer_weekly_tasks(db, now)
        outbox.letters.clear()   # the bell shows the task of the week; no mail to fictional addresses
        await db.commit()
        print(f"demo activity: tests={tests} needs={needs} offers={offers} applications={apps} "
              f"weekly_tasks={weekly}")


if __name__ == "__main__":
    asyncio.run(main())
