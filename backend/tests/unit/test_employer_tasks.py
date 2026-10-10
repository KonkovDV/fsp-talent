"""Employer tasks: answer checking, who sees what, the card signal; the message thread's access rule."""
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.v1.messages import can_post, thread_side
from app.api.v1.tasks import TaskCreate
from app.models import EmployerTask, Offer, Participant, TaskSubmission
from app.services.search.pipeline import days_ago
from app.services.tasks import (
    accepts_answers,
    candidate_view,
    card_signal,
    check_answer,
    graded_by,
    record_verdict,
    validate_reference,
    visible_to,
)


def _task(**kw) -> EmployerTask:
    base = dict(id=uuid.uuid4(), employer_id=uuid.uuid4(), title="Сколько раз выполнится цикл",
                statement="Дан цикл ...", answer_type="number", options=[], correct_index=None,
                reference_number="42", visibility="public", specialization="backend", candidate_id=None,
                deadline=None, is_open=True, created_at=datetime.now(UTC), vacancy_id=None)
    base.update(kw)
    return EmployerTask(**base)


def _person(spec="backend") -> Participant:
    return Participant(id=uuid.uuid4(), specialization=spec)


# --- checking ---------------------------------------------------------------------------------------

def test_number_answer_is_checked_against_the_reference():
    task = _task()
    assert check_answer(task, " 42 ", None).passed is True
    assert check_answer(task, "−42", None).passed is False
    assert check_answer(task, "сорок два", None).passed is False
    assert check_answer(task, "42", None).status == "checked"
    with pytest.raises(ValueError):
        check_answer(task, "  ", None)


def test_choice_answer_is_checked_and_out_of_range_refused():
    task = _task(answer_type="choice", options=["O(n)", "O(n log n)", "O(1)"], correct_index=1, reference_number=None)
    assert check_answer(task, None, 1).passed is True
    assert check_answer(task, None, 0).passed is False
    for bad in (None, 3, -1):
        with pytest.raises(ValueError):
            check_answer(task, None, bad)


def test_open_answer_waits_for_the_employer():
    task = _task(answer_type="open", reference_number=None)
    checked = check_answer(task, "Сначала профилирую запрос, потом добавлю индекс", None)
    assert checked.status == "review" and checked.passed is None
    with pytest.raises(ValueError):
        check_answer(task, "", None)
    with pytest.raises(ValueError):
        check_answer(task, "x" * 4001, None)


def test_a_pattern_is_checked_by_the_system_and_a_model_is_not_a_marker():
    task = SimpleNamespace(answer_type="regex", reference_number=r"FSP[0-9]{3}")
    assert check_answer(task, "FSP001", None).passed is True
    assert check_answer(task, "FSP001x", None).passed is False
    assert graded_by("regex") == "auto"
    assert graded_by("open") == "reviewer"
    validate_reference("regex", [], None, r"FSP[0-9]{3}")
    with pytest.raises(ValueError):
        validate_reference("regex", [], None, "(.*)*")


def test_employer_reference_is_validated():
    validate_reference("number", [], None, "17")
    validate_reference("open", [], None, None)
    validate_reference("choice", ["a", "b"], 0, None)
    for args in (("number", [], None, None), ("number", [], None, "1.5"), ("choice", ["a"], 0, None),
                 ("choice", ["a", "a"], 0, None), ("choice", ["a", "b"], 2, None), ("choice", ["a", " "], 0, None)):
        with pytest.raises(ValueError):
            validate_reference(*args)


def test_create_payload_needs_an_audience():
    common = dict(title="Задача", statement="Условие задачи длиннее десяти символов", answer_type="open")
    with pytest.raises(ValidationError):
        TaskCreate(**common, visibility="public")                      # no specialization
    with pytest.raises(ValidationError):
        TaskCreate(**common, visibility="public", specialization="astrology")
    with pytest.raises(ValidationError):
        TaskCreate(**common, visibility="addressed")                    # no candidate
    with pytest.raises(ValidationError):
        TaskCreate(**common, visibility="public", specialization="backend",
                   deadline=datetime.now(UTC) - timedelta(hours=1))
    ok = TaskCreate(**common, visibility="addressed", candidate_id=uuid.uuid4())
    assert ok.visibility == "addressed"
    code = {**common, "answer_type": "code"}
    lab = TaskCreate(**code, reference_number="sum_positive", visibility="public", specialization="backend")
    assert lab.answer_type == "code" and lab.reference_number == "sum_positive"
    with pytest.raises(ValidationError):
        TaskCreate(**code, reference_number="missing", visibility="public", specialization="backend")


# --- access -----------------------------------------------------------------------------------------

def test_public_task_is_for_its_specialization_only():
    task = _task(specialization="backend")
    assert visible_to(task, _person("backend"))
    assert not visible_to(task, _person("frontend"))
    assert not visible_to(task, _person(None))


def test_addressed_task_is_only_for_its_candidate():
    me, other = _person(), _person()
    task = _task(visibility="addressed", candidate_id=me.id)
    assert visible_to(task, me)
    assert not visible_to(task, other)   # same specialization does not open someone else's task


def test_closed_or_overdue_task_takes_no_answers():
    now = datetime.now(UTC)
    assert accepts_answers(_task(), now)
    assert not accepts_answers(_task(is_open=False), now)
    assert not accepts_answers(_task(deadline=now - timedelta(minutes=1)), now)
    assert accepts_answers(_task(deadline=now + timedelta(days=1)), now)


def test_reference_is_hidden_until_the_candidates_own_answer_is_checked():
    for task in (_task(), _task(answer_type="choice", options=["a", "b"], correct_index=1, reference_number=None)):
        before = candidate_view(task, "Сибирский код", None)
        assert "reference" not in before and "correct_index" not in before and "reference_number" not in before
        assert before["accepts_answers"] is True
        sub = TaskSubmission(id=uuid.uuid4(), status="checked", passed=False, submitted_at=datetime.now(UTC))
        after = candidate_view(task, "Сибирский код", sub)
        assert after["reference"] in ("42", "b") and after["accepts_answers"] is False


def test_open_task_never_exposes_a_reference():
    task = _task(answer_type="open", reference_number=None)
    sub = TaskSubmission(id=uuid.uuid4(), status="review", passed=None, submitted_at=datetime.now(UTC))
    assert "reference" not in candidate_view(task, None, sub)


# --- the card ---------------------------------------------------------------------------------------

def test_verdict_becomes_a_fresh_line_on_the_card():
    p = _person()
    assert card_signal(p, days_ago) is None
    record_verdict(p, _task(title="Оптимизация SQL"), True, datetime.now(UTC) - timedelta(days=1))
    assert card_signal(p, days_ago) == "Задание работодателя «Оптимизация SQL»: зачтено, вчера"
    record_verdict(p, _task(title="Скрипт выгрузки"), False, datetime.now(UTC))
    assert card_signal(p, days_ago) == "Задание работодателя «Скрипт выгрузки»: не зачтено, сегодня"


# --- messages ---------------------------------------------------------------------------------------

def test_thread_belongs_to_the_two_sides_only():
    employer, candidate = uuid.uuid4(), uuid.uuid4()
    offer = Offer(employer_id=employer, candidate_id=candidate, status="accepted")
    assert thread_side(offer, "employer", employer) == "employer"
    assert thread_side(offer, "participant", candidate) == "participant"
    assert thread_side(offer, "employer", uuid.uuid4()) is None
    assert thread_side(offer, "participant", employer) is None   # an id of the other role is not enough
    assert can_post(offer)
    offer.contacts_revoked_at = datetime.now(UTC)
    assert not can_post(offer)
    assert not can_post(Offer(employer_id=employer, candidate_id=candidate, status="pending"))
