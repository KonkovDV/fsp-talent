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
STEP_BUDGET = 10_000
MAX_NODES = 800
GROW_DEPTH = 8
MAX_BITS = 60
MAX_SEQ = 10_000
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
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise LabError("Слишком длинное решение")
    if _grow_depth(tree) > GROW_DEPTH:
        raise LabError("Слишком глубокое выражение")
    return tree


def _grow_depth(node: ast.AST) -> int:
    """How many times an expression can double a list or a number in one line."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
        return 1 + max(_grow_depth(node.left), _grow_depth(node.right))
    return max((_grow_depth(child) for child in ast.iter_child_nodes(node)), default=0)


def _too_big(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value.bit_length() > MAX_BITS
    if isinstance(value, str):
        return len(value) > MAX_SEQ
    if isinstance(value, (list, tuple)):
        return len(value) > MAX_SEQ
    return False


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


def child_cwd() -> str:
    """Outside the API directory, so a later import cannot read its .env."""
    for key in ("TEMP", "TMP", "TMPDIR"):
        value = os.environ.get(key)
        if value and Path(value).is_dir():
            return value
    return "/tmp"


def _run_cases(source: str, cases: list[list[Any]]) -> list[int | None]:
    """Run ``solve`` on every case in one process. Expected values are not sent across."""
    blank: list[int | None] = [None] * len(cases)
    payload = json.dumps({"source": source, "cases": cases}, ensure_ascii=False).encode("utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "app.services.code_lab", "--child"],
            input=payload, capture_output=True, timeout=RUN_TIMEOUT_S, check=False,
            env=child_env(), cwd=child_cwd(),
        )
    except subprocess.TimeoutExpired:
        return blank
    if proc.returncode != 0 or len(proc.stdout) > 4096:
        return blank
    try:
        got = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return blank
    if not isinstance(got, list) or len(got) != len(cases):
        return blank
    out: list[int | None] = []
    for item in got:
        if isinstance(item, bool) or not isinstance(item, int) or item.bit_length() > MAX_BITS:
            out.append(None)
        else:
            out.append(item)
    return out


def run_problem(problem_id: str, source: str) -> dict[str, Any]:
    """Check public and hidden cases. Hidden expected numbers are not in the result."""
    row = _PROBLEMS.get(problem_id)
    if row is None:
        raise LabError("Такого задания в лаборатории нет")
    guard(source)
    public_cases = [list(args) for args, _fn in row["public"]]
    hidden_cases = [list(args) for args, _fn in row["hidden"]]
    got = _run_cases(source, public_cases + hidden_cases)
    public_got = got[:len(public_cases)]
    hidden_got = got[len(public_cases):]
    public_ok = [
        value is not None and value == fn(*args)
        for (args, fn), value in zip(row["public"], public_got, strict=True)
    ]
    hidden_passed = sum(
        1 for (args, fn), value in zip(row["hidden"], hidden_got, strict=True)
        if value is not None and value == fn(*args)
    )
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
        steps = 0

        def _trace(frame, event, _arg):
            nonlocal steps
            if event == "line" and frame.f_code.co_filename == "<lab>":
                steps += 1
                if steps > STEP_BUDGET:
                    raise RuntimeError("steps")
                for value in frame.f_locals.values():
                    if _too_big(value):
                        raise RuntimeError("size")
            return _trace

        sys.settrace(_trace)
        exec(compile(tree, "<lab>", "exec"), ns, ns)  # noqa: S102 — guarded source, separate process
        results = []
        for args in msg["cases"]:
            out = ns["solve"](*args)
            if isinstance(out, bool) or not isinstance(out, int) or _too_big(out):
                results.append(None)
            else:
                results.append(out)
        sys.settrace(None)
        sys.stdout.write(json.dumps(results))
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    if "--child" in sys.argv:
        _child()
