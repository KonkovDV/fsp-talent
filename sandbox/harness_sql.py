"""Run one SELECT on a fresh memory database. The fixture SQL is an input, not the answer."""
import json
import sqlite3
import sys


def main() -> None:
    msg = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    source = " ".join(str(msg.get("source") or "").split())
    head = source.lower()
    if not head.startswith("select ") or ";" in source:
        sys.exit(1)
    out = []
    for case in msg.get("cases") or []:
        setup = case[0] if isinstance(case, list) and case and isinstance(case[0], str) else ""
        value = None
        try:
            con = sqlite3.connect(":memory:")
            if setup:
                con.executescript(setup)
            row = con.execute(source).fetchone()
            if row and isinstance(row[0], int) and not isinstance(row[0], bool):
                value = row[0]
        except Exception:
            value = None
        out.append(value)
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
