"""Check a jury pack of demo profiles. The command does not write to the database.

    python -m app.validation.jury_pack pack.json
    python -m app.validation.jury_pack pack.csv

JSON is a list of objects. CSV has a header: email, role, display_name, company, grade.
Roles are the two accounts that can log in: participant and employer. A public visitor
does not need an account.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROLES = {"participant", "employer"}
GRADES = {"intern", "junior", "middle", "senior", "lead"}


def validate_rows(rows: list) -> list[str]:
    if not isinstance(rows, list) or not rows:
        return ["Файл должен содержать непустой список профилей"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append(f"Строка {index}: ожидается объект")
            continue
        email = str(row.get("email") or "").strip().lower()
        role = row.get("role")
        if role not in ROLES:
            errors.append(f"Строка {index}: роль должна быть participant или employer")
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append(f"Строка {index}: нужен email")
        elif email in seen:
            errors.append(f"Строка {index}: email повторяется")
        seen.add(email)
        if role == "participant":
            if not str(row.get("display_name") or "").strip():
                errors.append(f"Строка {index}: нет имени")
            if row.get("grade") not in GRADES:
                errors.append(f"Строка {index}: неизвестный грейд")
        if role == "employer" and not str(row.get("company") or "").strip():
            errors.append(f"Строка {index}: нет названия компании")
    return errors


def load_pack(path: Path) -> list:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(text.splitlines()))
    data = json.loads(text)
    if isinstance(data, dict) and "profiles" in data:
        return data["profiles"]
    return data


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Укажите файл JSON или CSV")
    path = Path(sys.argv[1])
    errors = validate_rows(load_pack(path))
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"профилей: {len(load_pack(path))}, ошибок нет. В базу ничего не записано.")


if __name__ == "__main__":
    main()
