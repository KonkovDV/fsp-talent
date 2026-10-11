"""One practice run: a fresh directory, a child with hard limits, outputs back as JSON.

The container has no network. The limits here keep one run from starving the next one.
The caller sends inputs only; expected values never reach this process.
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WALL_S = 3.0
CPU_S = 2
FILE_BYTES = 1 << 20
PY_MEMORY = 256 << 20
MAX_STDOUT = 4096
MAX_BITS = 60
MAX_CASES = 64

COMMANDS = {
    "python": [sys.executable, "-I", "-S", str(HERE / "harness.py")],
    "javascript": ["node", "--max-old-space-size=64", "--disallow-code-generation-from-strings",
                   str(HERE / "harness.js")],
    "sql": [sys.executable, "-I", "-S", str(HERE / "harness_sql.py")],
}


def available_languages() -> list[str]:
    out = ["python", "sql"]
    if shutil.which("node"):
        out.append("javascript")
    return out


def _limits(language: str):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_S, CPU_S))
        resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_BYTES, FILE_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # V8 reserves far more address space than it uses; Node is held by its heap flag and the container.
        if language in ("python", "sql"):
            resource.setrlimit(resource.RLIMIT_AS, (PY_MEMORY, PY_MEMORY))
            # Audit M-1: the harness never forks or starts threads. With NPROC 0 the kernel refuses
            # every fork and clone of this uid's child, so nothing can setsid() out of the group that
            # killpg ends, and one run cannot eat the container's pids_limit. Node needs its V8
            # threads, so it stays under pids_limit and the container instead.
            resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    return apply


def _clean(values: object, count: int) -> list[int | None] | None:
    if not isinstance(values, list) or len(values) != count:
        return None
    out: list[int | None] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or value.bit_length() > MAX_BITS:
            out.append(None)
        else:
            out.append(value)
    return out


def run(language: str, source: str, cases: list) -> dict:
    """{"outputs": [...], "timed_out": bool}. A crash is a list of nulls, not a timeout."""
    if language not in available_languages():
        return {"error": "language"}
    if not isinstance(cases, list) or len(cases) > MAX_CASES:
        return {"error": "cases"}
    blank: list[int | None] = [None] * len(cases)
    payload = json.dumps({"source": source, "cases": cases}, ensure_ascii=False).encode("utf-8")
    work = tempfile.mkdtemp(prefix="run-")
    try:
        proc = subprocess.Popen(
            COMMANDS[language], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=work, env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": work},
            preexec_fn=_limits(language), start_new_session=True,
        )
        try:
            out, _ = proc.communicate(payload, timeout=WALL_S)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            return {"outputs": blank, "timed_out": True}
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        # SIGXCPU or SIGKILL from the CPU limit, or exit 2 from the harness: a limit, not a wrong answer.
        if proc.returncode in (2, -signal.SIGXCPU, -signal.SIGKILL):
            return {"outputs": blank, "timed_out": True}
        if proc.returncode != 0 or len(out) > MAX_STDOUT:
            return {"outputs": blank, "timed_out": False}
        try:
            got = json.loads(out.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"outputs": blank, "timed_out": False}
        clean = _clean(got, len(cases))
        return {"outputs": clean if clean is not None else blank, "timed_out": False}
    finally:
        shutil.rmtree(work, ignore_errors=True)
