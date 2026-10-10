import json
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[3] / "sandbox" / "harness_sql.py"


def _run(source: str, cases: list) -> list:
    proc = subprocess.run(
        [sys.executable, str(HARNESS)],
        input=json.dumps({"source": source, "cases": cases}).encode(),
        capture_output=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.decode())


def test_a_select_sees_the_fixture_and_a_write_is_refused():
    fixture = "create table nums(n integer); insert into nums values (1), (-2), (3);"
    assert _run("select sum(n) from nums", [[fixture]]) == [2]
    proc = subprocess.run(
        [sys.executable, str(HARNESS)],
        input=json.dumps({"source": "delete from nums", "cases": [[fixture]]}).encode(),
        capture_output=True, check=False,
    )
    assert proc.returncode == 1
