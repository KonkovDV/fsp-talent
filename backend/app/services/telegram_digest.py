"""Read-only lines for a messenger. No name, no contacts, and no grade from sport results."""
from __future__ import annotations

import re

_FSP_ID = re.compile(r"FSP[0-9]{3,6}")


def clean_fsp_id(raw: str) -> str | None:
    text = raw.strip().upper()
    return text if _FSP_ID.fullmatch(text) else None


def achievement_digest(fsp_id: str, rows: list[dict]) -> dict:
    items = [
        {"discipline": row["discipline"], "year": row["year"], "bucket": row["bucket"], "status": row["status"]}
        for row in rows[:8]
    ]
    lines = [f"ФСП ID {fsp_id}"]
    if items:
        lines.extend(f"{item['discipline']}, {item['year']}, {item['bucket']}, {item['status']}" for item in items)
    else:
        lines.append("Протоколов нет.")
    lines.append("Грейд этим списком не ставится.")
    return {"fsp_id": fsp_id, "text": "\n".join(lines), "items": items}


def vacancy_digest(rows: list[dict]) -> dict:
    items = []
    lines = ["Открытые вакансии"]
    for row in rows[:8]:
        items.append({
            "company": row["company"], "title": row["title"], "role": row.get("role"),
            "grade": row.get("grade"), "work_format": row.get("work_format"),
            "salary_from": row.get("salary_from"), "salary_to": row.get("salary_to"),
        })
        money = ""
        if row.get("salary_from") or row.get("salary_to"):
            money = f", {row.get('salary_from') or '…'}–{row.get('salary_to') or '…'} до НДФЛ"
        lines.append(f"{row['company']} — {row['title']}{money}")
    if not items:
        lines.append("Открытых вакансий нет.")
    lines.append("Имён кандидатов здесь нет.")
    return {"text": "\n".join(lines), "items": items}
