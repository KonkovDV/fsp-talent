"""Practice problems whose hidden cases do not move the grade or the match score.

The candidate writes one function, ``solve``. The process that runs it is a separate interpreter
with a three-second limit. Hidden expected values stay in this module and are not returned.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

CODE_LIMIT = 16 * 1024
RUN_TIMEOUT_S = 3
_CALLS = frozenset({
    "abs", "min", "max", "sum", "len", "range", "enumerate", "int", "bool",
    "list", "tuple", "sorted", "reversed", "zip", "all", "any", "str", "solve",
})


class LabError(ValueError):
    """The source is not a practice solution. The API shows this text."""


def guard(source: str) -> ast.Module:
    """Accept a single ``solve`` and refuse imports, attributes and other calls."""
    if len(source.encode("utf-8")) > CODE_LIMIT:
        raise LabError("Код длиннее 16 КиБ")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise LabError("В коде синтаксическая ошибка") from exc
    if not tree.body or any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise LabError("Нужна одна функция solve и ничего больше")
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(funcs) != 1 or funcs[0].name != "solve":
        raise LabError("Нужна одна функция solve")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Attribute, ast.Global, ast.Nonlocal,
                             ast.Lambda, ast.ClassDef, ast.Try, ast.With, ast.Raise, ast.Delete,
                             ast.Await, ast.Yield, ast.YieldFrom)):
            raise LabError("Такая конструкция в лаборатории недоступна")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            raise LabError("Возведение в степень в лаборатории недоступно")
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and abs(node.value) > 100_000:
            raise LabError("Слишком большое число")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _CALLS:
                raise LabError("Этот вызов в лаборатории недоступен")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise LabError("Служебные имена недоступны")
    return tree


def _sum_positive(xs: list[int]) -> int:
    return sum(x for x in xs if isinstance(x, int) and not isinstance(x, bool) and x > 0)


def _count_long(words: list[str], n: int) -> int:
    return sum(1 for word in words if isinstance(word, str) and len(word) > n)


def _clamp(value: int, low: int, high: int) -> int:
    return min(high, max(low, value))


Case = tuple[list[Any], Callable[..., int]]

# Public pairs are described in the statement. Hidden pairs are only counted.
_PROBLEMS: dict[str, dict[str, Any]] = {
    "sum_positive": {
        "title": "Сумма положительных",
        "statement": (
            "Напишите функцию solve(xs). Она получает список целых и возвращает сумму положительных. "
            "Ноль и отрицательные в сумму не входят. Пустой список даёт 0.\n"
            "Открытый пример: solve([1, -2, 3]) == 4."
        ),
        "public": [(([1, -2, 3],), _sum_positive), (([],), _sum_positive)],
        "hidden": [(([0, 5, 5],), _sum_positive), (([-1, -2],), _sum_positive), (([100],), _sum_positive)],
    },
    "count_long": {
        "title": "Длинные слова",
        "statement": (
            "Напишите функцию solve(words, n). Она считает, сколько строк в списке длиннее n. "
            "Открытый пример: solve([\"кот\", \"программа\"], 3) == 1."
        ),
        "public": [([["кот", "программа"], 3], _count_long)],
        "hidden": [([[], 1], _count_long), ([["aa", "bbbb"], 2], _count_long)],
    },
    "clamp": {
        "title": "Ограничить число",
        "statement": (
            "Напишите функцию solve(value, low, high). Она возвращает value, если оно между low и high, "
            "иначе ближайшую границу. Открытый пример: solve(12, 0, 10) == 10."
        ),
        "public": [([12, 0, 10], _clamp), ([3, 0, 10], _clamp)],
        "hidden": [([-4, 0, 10], _clamp), ([10, 0, 10], _clamp)],
    },
}


def problem_ids() -> list[str]:
    return list(_PROBLEMS)


def problem_public(problem_id: str) -> dict[str, str] | None:
    row = _PROBLEMS.get(problem_id)
    if row is None:
        return None
    return {"id": problem_id, "title": row["title"], "statement": row["statement"]}


def child_env() -> dict[str, str]:
    """The practice process sees the interpreter, not the API's secrets."""
    root = str(Path(__file__).resolve().parents[2])
    env = {"PYTHONPATH": root, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    for key in ("PATH", "SYSTEMROOT", "WINDIR", "PATHEXT"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _run_once(source: str, args: list[Any]) -> tuple[bool, int | None]:
    """Run ``solve`` on one argument list. The expected value is not sent to the child."""
    payload = json.dumps({"source": source, "args": args}, ensure_ascii=False).encode("utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "app.services.code_lab", "--child"],
            input=payload, capture_output=True, timeout=RUN_TIMEOUT_S, check=False,
            env=child_env(),
        )
    except subprocess.TimeoutExpired:
        return False, None
    if proc.returncode != 0:
        return False, None
    try:
        got = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, None
    if isinstance(got, bool) or not isinstance(got, int):
        return False, None
    return True, got


def run_problem(problem_id: str, source: str) -> dict[str, Any]:
    """Check public and hidden cases. Hidden expected numbers are not in the result."""
    row = _PROBLEMS.get(problem_id)
    if row is None:
        raise LabError("Такого задания в лаборатории нет")
    guard(source)
    public_ok = []
    for args, fn in row["public"]:
        ran, got = _run_once(source, list(args))
        public_ok.append(ran and got == fn(*args))
    hidden_passed = 0
    for args, fn in row["hidden"]:
        ran, got = _run_once(source, list(args))
        if ran and got == fn(*args):
            hidden_passed += 1
    hidden_total = len(row["hidden"])
    passed = all(public_ok) and hidden_passed == hidden_total
    return {
        "passed": passed,
        "public_ok": public_ok,
        "hidden_passed": hidden_passed,
        "hidden_total": hidden_total,
        "practice_only": True,
    }


def _child() -> None:
    raw = sys.stdin.buffer.read()
    try:
        msg = json.loads(raw.decode("utf-8"))
        tree = guard(msg["source"])
        safe = {name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
                for name in _CALLS if name != "solve"}
        ns: dict[str, Any] = {"__builtins__": safe}
        exec(compile(tree, "<lab>", "exec"), ns, ns)  # noqa: S102 — guarded source, separate process
        out = ns["solve"](*msg["args"])
        if isinstance(out, bool) or not isinstance(out, int):
            raise LabError("solve должна вернуть целое число")
        sys.stdout.write(json.dumps(out))
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    if "--child" in sys.argv:
        _child()
