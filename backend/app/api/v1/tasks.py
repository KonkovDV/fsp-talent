"""Employer tasks: the employer writes, the candidate answers, the system or the employer checks.

Access:
- an employer sees and manages only own tasks and their answers;
- a candidate sees public tasks of own specialization and tasks addressed to them, nothing else
  (another candidate's addressed task is 404, as if it did not exist);
- the reference answer never leaves the server before the candidate's own answer is checked.
Letters carry no personal data of the other side: the employer reads the anonymous category only.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_employer, get_current_participant
from app.api.errors import ApiError
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.models import CategoryAssignment, Employer, EmployerTask, Participant, TaskSubmission, Vacancy
from app.services.code_lab import problem_ids, problem_public
from app.services.code_mark import copy_mark
from app.services.notify import Outbox, category_label, notify
from app.services.sandbox import SandboxUnavailable
from app.services.survey import SPECIALIZATIONS
from app.services.tasks import (
    MAX_CODE,
    accepts_answers,
    candidate_view,
    check_answer,
    employer_view,
    record_verdict,
    stored_reference,
    submission_view,
    validate_reference,
    visible_to,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

TASKS_PER_DAY = 30


def _sub(current: dict) -> uuid.UUID:
    return uuid.UUID(current["sub"])


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    statement: str = Field(min_length=10, max_length=4000)
    answer_type: Literal["number", "choice", "open", "code"]
    options: Annotated[list[Annotated[str, Field(max_length=300)]], Field(max_length=8)] = Field(default_factory=list)
    correct_index: int | None = Field(None, ge=0, le=7)
    reference_number: str | None = Field(None, max_length=40)
    visibility: Literal["public", "addressed"]
    specialization: str | None = Field(None, max_length=30)
    candidate_id: uuid.UUID | None = None
    vacancy_id: uuid.UUID | None = None
    deadline: datetime | None = None

    @model_validator(mode="after")
    def _shape(self):
        validate_reference(self.answer_type, self.options, self.correct_index, self.reference_number)
        if self.visibility == "public" and self.specialization not in SPECIALIZATIONS:
            raise ValueError("Для общего задания выберите специализацию")
        if self.visibility == "addressed" and self.candidate_id is None:
            raise ValueError("Для адресного задания нужен кандидат")
        if self.deadline is not None:
            if self.deadline.tzinfo is None:
                self.deadline = self.deadline.replace(tzinfo=UTC)
            if self.deadline <= datetime.now(UTC):
                raise ValueError("Срок сдачи уже прошёл")
        return self


@router.post("/", status_code=201)
async def create_task(body: TaskCreate, current: dict = Depends(get_current_employer),
                      db: AsyncSession = Depends(get_db)):
    employer = await db.get(Employer, _sub(current))
    if employer is None:
        raise ApiError(404, "not_found", "Работодатель не найден")
    # Employers are not verified in the MVP: cap how many tasks one account writes per day.
    if await too_many(f"tasks:create:{employer.id}", limit=TASKS_PER_DAY, window_seconds=86_400):
        raise ApiError(429, "rate_limited", "Лимит заданий на сегодня исчерпан")
    if body.vacancy_id is not None:
        vacancy = await db.get(Vacancy, body.vacancy_id)
        if vacancy is None or vacancy.employer_id != employer.id:
            raise ApiError(404, "not_found", "Вакансия не найдена")
    candidate = None
    if body.visibility == "addressed":
        candidate = await db.get(Participant, body.candidate_id)
        if candidate is None or candidate.deleted_at is not None or not candidate.discoverable:
            raise ApiError(404, "not_found", "Кандидат недоступен")
    task = EmployerTask(
        employer_id=employer.id, vacancy_id=body.vacancy_id, title=body.title.strip(),
        statement=body.statement.strip(), answer_type=body.answer_type,
        options=[o.strip() for o in body.options] if body.answer_type == "choice" else [],
        correct_index=body.correct_index if body.answer_type == "choice" else None,
        reference_number=stored_reference(body.answer_type, body.reference_number),
        visibility=body.visibility,
        specialization=body.specialization if body.visibility == "public" else (candidate.specialization or None),
        candidate_id=candidate.id if candidate else None, deadline=body.deadline,
        created_at=datetime.now(UTC),
    )
    db.add(task)
    await db.flush()
    outbox = Outbox()
    if candidate is not None:
        check = "Ответ проверит система." if body.answer_type != "open" else "Ответ проверит работодатель."
        await notify(db, outbox, "participant", candidate.id, "task_new",
                     f"Задание от «{employer.company_name}»",
                     f"Компания предлагает вам задание «{task.title}». {check} Грейд оно не меняет, "
                     "а результат появится в вашей карточке для работодателей.",
                     f"/candidate/tasks?task={task.id}")
    await db.commit()
    await outbox.deliver()
    return employer_view(task)


async def _counts(db: AsyncSession, task_ids: list[uuid.UUID]) -> dict:
    if not task_ids:
        return {}
    rows = await db.execute(
        select(TaskSubmission.task_id, func.count(),
               func.sum(case((TaskSubmission.passed.is_(True), 1), else_=0)),
               func.sum(case((TaskSubmission.status == "review", 1), else_=0)))
        .where(TaskSubmission.task_id.in_(task_ids)).group_by(TaskSubmission.task_id))
    return {tid: {"total": total, "passed": int(ok or 0), "review": int(wait or 0)}
            for tid, total, ok, wait in rows}


@router.get("/lab")
async def lab_catalog(current: dict = Depends(get_current_employer)):
    """Practice problems an employer can attach. Hidden cases are not in this list."""
    del current
    return [problem_public(pid) for pid in problem_ids()]


@router.get("/mine")
async def my_tasks(current: dict = Depends(get_current_employer), db: AsyncSession = Depends(get_db)):
    tasks = list(await db.scalars(select(EmployerTask).where(EmployerTask.employer_id == _sub(current))
                                  .order_by(EmployerTask.created_at.desc())))
    counts = await _counts(db, [t.id for t in tasks])
    return [employer_view(t, counts.get(t.id)) for t in tasks]


async def _own_task(db: AsyncSession, task_id: uuid.UUID, employer_id: uuid.UUID, lock: bool = False) -> EmployerTask:
    task = await db.get(EmployerTask, task_id, with_for_update=lock)
    if task is None or task.employer_id != employer_id:
        raise ApiError(404, "not_found", "Задание не найдено")
    return task


@router.get("/{task_id}/submissions")
async def task_submissions(task_id: uuid.UUID, current: dict = Depends(get_current_employer),
                           db: AsyncSession = Depends(get_db)):
    """Answers to the employer's own task. Who answered is the anonymous category, as on the search card."""
    task = await _own_task(db, task_id, _sub(current))
    rows = list(await db.scalars(select(TaskSubmission).where(TaskSubmission.task_id == task.id)
                                 .order_by(TaskSubmission.submitted_at.desc())))
    cats = {c.participant_id: c for c in await db.scalars(select(CategoryAssignment).where(
        CategoryAssignment.participant_id.in_([s.participant_id for s in rows])))} if rows else {}
    out = []
    for s in rows:
        cat = cats.get(s.participant_id)
        out.append({**submission_view(s), "candidate_id": str(s.participant_id),
                    "candidate": category_label(cat.primary_role if cat else None, cat.grade if cat else None)})
    return {"task": employer_view(task), "submissions": out}


@router.post("/{task_id}/close")
async def close_task(task_id: uuid.UUID, current: dict = Depends(get_current_employer),
                     db: AsyncSession = Depends(get_db)):
    task = await _own_task(db, task_id, _sub(current), lock=True)
    task.is_open = False
    await db.commit()
    return employer_view(task)


class ReviewIn(BaseModel):
    passed: bool
    comment: str | None = Field(None, max_length=1000)


@router.post("/submissions/{submission_id}/review")
async def review_submission(submission_id: uuid.UUID, body: ReviewIn, current: dict = Depends(get_current_employer),
                            db: AsyncSession = Depends(get_db)):
    """The employer's verdict on an open answer: зачтено / не зачтено and a short comment."""
    sub = await db.get(TaskSubmission, submission_id, with_for_update=True)
    task = await db.get(EmployerTask, sub.task_id) if sub else None
    if sub is None or task is None or task.employer_id != _sub(current):
        raise ApiError(404, "not_found", "Ответ не найден")
    if sub.status == "checked":
        raise ApiError(409, "conflict", "Этот ответ проверила система")
    now = datetime.now(UTC)
    sub.status, sub.passed, sub.reviewed_at = "reviewed", body.passed, now
    sub.comment = (body.comment or "").strip() or None
    participant = await db.get(Participant, sub.participant_id)
    employer = await db.get(Employer, task.employer_id)
    outbox = Outbox()
    if participant is not None and participant.deleted_at is None:
        record_verdict(participant, task, body.passed, now)
        verdict = "зачтено" if body.passed else "не зачтено"
        await notify(db, outbox, "participant", participant.id, "task_reviewed",
                     f"«{employer.company_name}» проверила ваш ответ",
                     f"Задание «{task.title}»: {verdict}." + (" Есть комментарий." if sub.comment else ""),
                     f"/candidate/tasks?task={task.id}")
    await db.commit()
    await outbox.deliver()
    return submission_view(sub)


# ── candidate side ──────────────────────────────────────────────────────────

def _for_candidate(participant: Participant):
    """Public tasks of the candidate's specialization and tasks addressed to them."""
    cond = EmployerTask.candidate_id == participant.id
    if participant.specialization:
        cond = or_(cond, (EmployerTask.visibility == "public")
                   & (EmployerTask.specialization == participant.specialization))
    return cond


@router.get("/for-me")
async def tasks_for_me(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    participant = await db.get(Participant, _sub(current))
    if participant is None or participant.deleted_at is not None:
        raise ApiError(404, "not_found", "Профиль не найден")
    rows = list((await db.execute(
        select(EmployerTask, Employer.company_name).join(Employer, Employer.id == EmployerTask.employer_id)
        .where(_for_candidate(participant)).order_by(EmployerTask.created_at.desc()).limit(100))).all())
    mine = {s.task_id: s for s in await db.scalars(select(TaskSubmission).where(
        TaskSubmission.participant_id == participant.id,
        TaskSubmission.task_id.in_([t.id for t, _ in rows])))} if rows else {}
    now = datetime.now(UTC)
    out = []
    for task, company in rows:
        if not visible_to(task, participant):
            continue
        submission = mine.get(task.id)
        # A closed task the candidate never answered is no longer on the list.
        if submission is None and not accepts_answers(task, now):
            continue
        out.append(candidate_view(task, company, submission, now))
    return out


class AnswerIn(BaseModel):
    answer_text: str | None = Field(None, max_length=MAX_CODE)
    answer_index: int | None = Field(None, ge=0, le=7)
    language: Literal["python", "javascript"] = "python"


@router.post("/{task_id}/answer")
async def answer_task(task_id: uuid.UUID, body: AnswerIn, current: dict = Depends(get_current_participant),
                      db: AsyncSession = Depends(get_db)):
    participant = await db.get(Participant, _sub(current))
    task = await db.get(EmployerTask, task_id)
    if participant is None or task is None or not visible_to(task, participant):
        raise ApiError(404, "not_found", "Задание не найдено")
    if await db.scalar(select(TaskSubmission.id).where(TaskSubmission.task_id == task.id,
                                                       TaskSubmission.participant_id == participant.id)):
        raise ApiError(409, "task_answered")
    if not accepts_answers(task):
        raise ApiError(409, "task_closed")
    try:
        # A code check waits up to the run limit; the event loop keeps serving other requests meanwhile.
        checked = await asyncio.to_thread(check_answer, task, body.answer_text, body.answer_index, body.language)
    except SandboxUnavailable as e:
        raise ApiError(503, "sandbox_unavailable", "Проверка кода временно недоступна. Ответ не сохранён.") from e
    except ValueError as e:
        detail = str(e).strip()
        if not detail or detail == "answer":
            detail = ("Ответ не подходит к заданию: введите число, "
                      "выберите вариант или опишите решение")
        raise ApiError(422, "validation_error", detail) from e
    now = datetime.now(UTC)
    notes = [checked.note] if checked.note else []
    if task.answer_type == "code" and checked.answer_text:
        others = list(await db.scalars(select(TaskSubmission.answer_text).where(
            TaskSubmission.task_id == task.id, TaskSubmission.answer_text.is_not(None))))
        if copy_mark(checked.answer_text, [text for text in others if text], body.language):
            notes.append(
                "Пометка для разбора: решение похоже на другое сданное. "
                "Проверка примеров от этого не меняется.")
    comment = "\n".join(notes) if notes else None
    sub = TaskSubmission(task_id=task.id, participant_id=participant.id, answer_text=checked.answer_text,
                         comment=comment,
                         answer_index=checked.answer_index, status=checked.status, passed=checked.passed,
                         submitted_at=now, reviewed_at=now if checked.status == "checked" else None)
    db.add(sub)
    try:
        await db.flush()
    except IntegrityError as e:   # a double click from two tabs
        await db.rollback()
        raise ApiError(409, "task_answered") from e
    if checked.passed is not None:
        record_verdict(participant, task, checked.passed, now)
    cat = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == participant.id))
    who = category_label(cat.primary_role if cat else None, cat.grade if cat else None)
    outbox = Outbox()
    if checked.status == "review":
        text = f"Кандидат ({who}) прислал решение. Оно ждёт вашей проверки: зачтено или нет и короткий комментарий."
    else:
        text = f"Кандидат ({who}) ответил, система проверила: {'верно' if checked.passed else 'неверно'}."
    await notify(db, outbox, "employer", task.employer_id, "task_submission",
                 f"Новый ответ на задание «{task.title}»", text, f"/employer/tasks?task={task.id}")
    await db.commit()
    await outbox.deliver()
    company = await db.scalar(select(Employer.company_name).where(Employer.id == task.employer_id))
    return candidate_view(task, company, sub)
