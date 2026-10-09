"""The practice lab checks a function and does not describe a grade."""
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.models import EmployerTask
from app.services.code_lab import (
    LabError,
    _seccomp_filter,
    child_cwd,
    child_env,
    guard,
    network_syscalls,
    run_problem,
)
from app.services.tasks import check_answer, stored_reference, validate_reference

SOLVE = "def solve(xs):\n    return sum(x for x in xs if x > 0)\n"


def test_a_correct_function_passes_hidden_cases_without_revealing_them():
    out = run_problem("sum_positive", SOLVE)
    assert out["passed"] is True and out["practice_only"] is True and out["timed_out"] is False
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
    assert Path(child_cwd()).resolve() != Path(__file__).resolve().parents[2]
    numbers = network_syscalls("x86_64")
    assert 41 in numbers and 288 in numbers
    assert _seccomp_filter(numbers)
    if sys.platform == "linux":
        probe = subprocess.run(
            [sys.executable, "-c",
             "import socket\n"
             "from app.services.code_lab import deny_network\n"
             "installed = deny_network()\n"
             "blocked = False\n"
             "try:\n"
             "    socket.socket()\n"
             "except OSError:\n"
             "    blocked = True\n"
             "raise SystemExit(0 if installed and blocked else 1)\n"],
            capture_output=True, timeout=15, check=False,
        )
        assert probe.returncode == 0, probe.stderr.decode("utf-8", "replace")


def test_imports_and_a_wrong_answer_do_not_pass():
    with pytest.raises(LabError):
        guard("import os\ndef solve(xs):\n    return 0\n")
    out = run_problem("sum_positive", "def solve(xs):\n    return 0\n")
    assert out["passed"] is False and out["practice_only"] is True and out["timed_out"] is False


def test_a_code_task_keeps_the_lab_problem_and_a_growing_loop_stops():
    assert stored_reference("code", " sum_positive ") == "sum_positive"
    assert stored_reference("number", "12") == "12"
    assert stored_reference("open", "sum_positive") is None
    assert stored_reference("choice", "x") is None
    expr = "x"
    for _ in range(9):
        expr = f"({expr}*{expr})"
    with pytest.raises(LabError):
        guard(f"def solve(xs):\n    x = 2\n    return {expr}\n")
    started = time.perf_counter()
    out = run_problem(
        "sum_positive",
        "def solve(xs):\n    x = 2\n    while True:\n        x = x * x\n    return x\n",
    )
    assert out["passed"] is False and out["practice_only"] is True and out["timed_out"] is True
    assert time.perf_counter() - started < 2


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
