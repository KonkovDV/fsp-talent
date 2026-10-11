"""Stand log: `RuntimeError: Event loop is closed` in deliver_webhooks. Every Celery task runs on a new
event loop, and pooled DB/Redis connections from the previous loop must not leak into the next one."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

SCRIPT = """
from app.workers.tasks import deliver_webhooks, run_async
from app.core.redis_client import get_redis

async def ping():
    return await (await get_redis()).ping()

for _ in range(3):
    deliver_webhooks.run()
    run_async(ping())
print("three passes ok")
"""


def test_tasks_run_back_to_back_in_one_worker_process():
    proc = subprocess.run([sys.executable, "-c", SCRIPT], cwd=BACKEND, env=dict(os.environ),
                          capture_output=True, text=True, timeout=120)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "three passes ok" in out
    assert "Event loop is closed" not in out and "attached to a different loop" not in out
