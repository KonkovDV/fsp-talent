"""Runs solve on each case and prints the outputs. Exit 2 means a limit was hit."""
import json
import sys


def main() -> None:
    sys.setrecursionlimit(2000)
    msg = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    ns: dict = {}
    try:
        exec(compile(msg["source"], "<solution>", "exec"), ns, ns)  # noqa: S102 — isolated container
        solve = ns["solve"]
        out = []
        for args in msg["cases"]:
            try:
                value = solve(*args)
            except (RecursionError, MemoryError):
                raise
            except Exception:
                value = None
            out.append(value if isinstance(value, int) and not isinstance(value, bool) else None)
    except (RecursionError, MemoryError):
        sys.exit(2)
    except Exception:
        sys.exit(1)
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
