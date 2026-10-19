#!/usr/bin/env python3
"""Check a pg_dump custom-format file without restoring it.

    python deploy/verify_backup.py deploy/backups/fsp_talent-YYYYMMDD-HHMM.dump

Exit 0 when the file is a custom dump and names the tables the product cannot start without.
"""
from __future__ import annotations

import sys
from pathlib import Path

MAGIC = b"PGDMP"
REQUIRED = (b"participants", b"employers", b"offers", b"test_sessions", b"consents")


def verify_dump(path: Path) -> list[str]:
    if not path.is_file():
        return ["файла нет"]
    data = path.read_bytes()
    errors = []
    if len(data) < 100:
        errors.append("файл слишком маленький для дампа")
    if not data.startswith(MAGIC):
        errors.append("это не дамп pg_dump -Fc")
    for name in REQUIRED:
        if name not in data:
            errors.append(f"в дампе нет таблицы {name.decode()}")
    return errors


def verify_key_dir(path: Path) -> list[str]:
    """The signing key must sit next to a dump before anyone calls the copy a restore set."""
    if not path.is_dir():
        return ["каталога ключей нет"]
    pem = path / "vc_ed25519.pem"
    if not pem.is_file() or pem.stat().st_size < 32:
        return ["в копии нет ключа подписи"]
    return []


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print("Нужен путь к .dump и, если ключи копировались, путь к каталогу ключей", file=sys.stderr)
        return 2
    errors = verify_dump(Path(argv[1]))
    if len(argv) == 3:
        errors.extend(verify_key_dir(Path(argv[2])))
    if errors:
        print("Дамп не прошёл проверку:", file=sys.stderr)
        for line in errors:
            print(f"- {line}", file=sys.stderr)
        return 1
    print(f"Дамп в порядке: {argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
