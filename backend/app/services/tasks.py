"""Tasks written by employers (TZ 2.1: regular tasks; client Q&A of 2026-10).

«Регулярное задание пишет работодатель. Если есть эталон ответа — проверяет система. Открытые задания
(скрипт, бизнес-решение) оценивает работодатель. Работодатель может предложить задание точечно конкретному
кандидату или выложить на общее обозрение.»

The pure rules live here so they can be tested without a database:
- who may see a task (`visible_to`), and when a task takes answers (`accepts_answers`);
- what the candidate may see before answering (`candidate_view`: never the reference);
- how an answer is checked (`check_answer`);
- the line the employer reads on the anonymous card (`card_signal`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.items import same_number, whole_number
from app.models import EmployerTask, Participant, TaskSubmission
from app.services.code_lab import LabError, problem_public, run_problem

ANSWER_TYPES = ("number", "choice", "open", "code")
MAX_ANSWER = 4000
MAX_CODE = 16 * 1024
STATUS_LABELS = {"checked": "проверено системой", "review": "на проверке", "reviewed": "проверено работодателем"}


def visible_to(task: EmployerTask, participant: Participant) -> bool:
    """A public task is for its specialization; an addressed one only for its candidate."""
    if task.visibility == "addressed":
        return task.candidate_id == participant.id
    return task.visibility == "public" and bool(participant.specialization) \
        and task.specialization == participant.specialization


def accepts_answers(task: EmployerTask, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return bool(task.is_open) and (task.deadline is None or task.deadline > now)


@dataclass
class Checked:
    status: str            # checked | review
    passed: bool | None    # None while the employer has not reviewed an open answer
    answer_text: str | None
    answer_index: int | None
    note: str | None = None  # a system mark; it does not change the grade


LIMIT_NOTE = (
    "Пометка системы: проверка оборвалась по лимиту лаборатории. "
    "Это не ошибка в примерах и грейд не меняет."
)


def case_note(outcome: dict) -> str:
    """How many examples passed. Hidden inputs and expected values stay on the server."""
    public = outcome.get("public_ok") or []
    return (f"Пометка системы: открытые примеры {sum(1 for ok in public if ok)} из {len(public)}, "
            f"скрытые {outcome.get('hidden_passed', 0)} из {outcome.get('hidden_total', 0)}.")


def check_answer(task: EmployerTask, answer_text: str | None, answer_index: int | None) -> Checked:
    """Number and choice are checked against the reference now; an open answer waits for the employer.

    ValueError means the answer does not fit the task type (the API turns it into 422).
    """
    if task.answer_type == "number":
        text = (answer_text or "").strip()
        if not text:
            raise ValueError("answer")
        return Checked("checked", same_number(text, task.reference_number or ""), text[:40], None)
    if task.answer_type == "choice":
        options = list(task.options or [])
        if answer_index is None or not 0 <= answer_index < len(options):
            raise ValueError("answer")
        return Checked("checked", answer_index == task.correct_index, None, answer_index)
    if task.answer_type == "code":
        text = (answer_text or "").strip()
        if not text or len(text) > MAX_CODE:
            raise ValueError("answer")
        try:
            outcome = run_problem(task.reference_number or "", text)
        except LabError as exc:
            raise ValueError(str(exc)) from exc
        return Checked("checked", bool(outcome["passed"]), text, None,
                       LIMIT_NOTE if outcome.get("timed_out") else case_note(outcome))
    text = (answer_text or "").strip()
    if not text or len(text) > MAX_ANSWER:
        raise ValueError("answer")
    return Checked("review", None, text, None)


def validate_reference(answer_type: str, options: list[str], correct_index: int | None,
                       reference_number: str | None) -> None:
    """The employer's own input: a number task needs an integer, a choice task 2–8 options and a right one."""
    if answer_type == "number":
        if not reference_number or not whole_number(reference_number):
            raise ValueError("Для ответа-числа укажите эталон: целое число")
    elif answer_type == "choice":
        clean = [o.strip() for o in options if o and o.strip()]
        if not 2 <= len(clean) <= 8 or len(clean) != len(options):
            raise ValueError("Для выбора ответа нужно от 2 до 8 непустых вариантов")
        if len(set(clean)) != len(clean):
            raise ValueError("Варианты ответа не должны повторяться")
        if correct_index is None or not 0 <= correct_index < len(options):
            raise ValueError("Отметьте правильный вариант")
    elif answer_type == "code":
        if problem_public(reference_number or "") is None:
            raise ValueError("Выберите задание лаборатории")
    elif answer_type != "open":
        raise ValueError("Неизвестный тип ответа")


def stored_reference(answer_type: str, reference_number: str | None) -> str | None:
    """A number keeps its key. A code task keeps the lab problem id. Other types keep neither."""
    if answer_type not in ("number", "code") or not reference_number or not reference_number.strip():
        return None
    return reference_number.strip()


def candidate_view(task: EmployerTask, company: str | None, mine: TaskSubmission | None,
                   now: datetime | None = None) -> dict:
    """What the candidate sees. The reference appears only after the candidate's own answer is checked."""
    out = {
        "id": str(task.id), "title": task.title, "statement": task.statement, "answer_type": task.answer_type,
        "options": [{"index": i, "text": t} for i, t in enumerate(task.options or [])]
        if task.answer_type == "choice" else [],
        "company": company, "addressed": task.visibility == "addressed",
        "vacancy_id": str(task.vacancy_id) if task.vacancy_id else None,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "accepts_answers": accepts_answers(task, now) and mine is None,
        "submission": submission_view(mine) if mine else None,
        "practice_only": task.answer_type == "code",
    }
    if mine is not None and mine.status == "checked":
        out["reference"] = (task.reference_number if task.answer_type == "number"
                            else (task.options or [])[task.correct_index] if task.correct_index is not None else None)
    return out


def submission_view(s: TaskSubmission) -> dict:
    return {
        "id": str(s.id), "status": s.status, "status_label": STATUS_LABELS.get(s.status, s.status),
        "passed": s.passed, "comment": s.comment, "answer_text": s.answer_text, "answer_index": s.answer_index,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
    }


def employer_view(task: EmployerTask, counts: dict | None = None) -> dict:
    """The owner sees everything, the reference included."""
    counts = counts or {}
    return {
        "id": str(task.id), "title": task.title, "statement": task.statement, "answer_type": task.answer_type,
        "options": list(task.options or []), "correct_index": task.correct_index,
        "reference_number": task.reference_number, "visibility": task.visibility,
        "specialization": task.specialization,
        "candidate_id": str(task.candidate_id) if task.candidate_id else None,
        "vacancy_id": str(task.vacancy_id) if task.vacancy_id else None,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "is_open": task.is_open, "accepts_answers": accepts_answers(task),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "lab_title": (problem_public(task.reference_number or "") or {}).get("title")
        if task.answer_type == "code" else None,
        "submissions": counts.get("total", 0), "passed": counts.get("passed", 0),
        "awaiting_review": counts.get("review", 0),
    }


def record_verdict(participant: Participant, task: EmployerTask, passed: bool, at: datetime) -> None:
    """The latest verdict becomes the fresh signal on the anonymous card."""
    participant.employer_task_title = task.title[:200]
    participant.employer_task_passed = passed
    participant.employer_task_at = at


def card_signal(participant: Participant, days_ago) -> str | None:
    """«Задание работодателя «…»: зачтено, вчера». days_ago is the search module's own formatter."""
    if participant.employer_task_at is None or not participant.employer_task_title:
        return None
    mark = "зачтено" if participant.employer_task_passed else "не зачтено"
    return (f"Задание работодателя «{participant.employer_task_title}»: {mark}, "
            f"{days_ago(participant.employer_task_at)}")

