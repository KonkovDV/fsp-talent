"""The practice lab checks a function and does not describe a grade."""
import uuid
from datetime import UTC, datetime

import pytest

from app.models import EmployerTask
from app.services.code_lab import LabError, child_env, guard, run_problem
from app.services.tasks import check_answer, validate_reference

SOLVE = "def solve(xs):\n    return sum(x for x in xs if x > 0)\n"


def test_a_correct_function_passes_hidden_cases_without_revealing_them():
    out = run_problem("sum_positive", SOLVE)
    assert out["passed"] is True and out["practice_only"] is True
    assert out["hidden_passed"] == out["hidden_total"] > 0
    assert "expected" not in out
    blob = str(out)
    assert "100" not in blob


def test_a_huge_number_or_a_power_is_refused_before_it_runs():
    with pytest.raises(LabError):
        guard("def solve(xs):\n    return 10 ** 8\n")
    with pytest.raises(LabError):
        guard("def solve(xs):\n    return [0] * 1000001\n")


def test_the_practice_process_does_not_inherit_the_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://secret")
    env = child_env()
    assert "DATABASE_URL" not in env
    assert "postgres://secret" not in env.values()
    assert "PYTHONPATH" in env


def test_imports_and_a_wrong_answer_do_not_pass():
    with pytest.raises(LabError):
        guard("import os\ndef solve(xs):\n    return 0\n")
    out = run_problem("sum_positive", "def solve(xs):\n    return 0\n")
    assert out["passed"] is False and out["practice_only"] is True


def test_a_code_task_is_checked_and_does_not_ask_for_a_grade():
    validate_reference("code", [], None, "sum_positive")
    with pytest.raises(ValueError):
        validate_reference("code", [], None, "missing")
    task = EmployerTask(
        id=uuid.uuid4(), employer_id=uuid.uuid4(), title="Сумма", statement="Напишите solve(xs).",
        answer_type="code", options=[], correct_index=None, reference_number="sum_positive",
        visibility="public", specialization="backend", created_at=datetime.now(UTC),
    )
    checked = check_answer(task, SOLVE, None)
    assert checked.status == "checked" and checked.passed is True
