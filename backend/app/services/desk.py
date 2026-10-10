"""Rules for the moderation desk. The printed jury employer cannot be switched off."""
from __future__ import annotations

import csv
import io

PROTECTED_EMAILS = frozenset({"hr@sibcode.demo"})


def can_suspend(actor_id, target_id, email: str | None) -> bool:
    if str(actor_id) == str(target_id):
        return False
    return (email or "") not in PROTECTED_EMAILS


def complaints_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "reason", "vacancy_id", "offer_id", "created_at"])
    for row in rows:
        writer.writerow([
            row["id"], row["reason"], row.get("vacancy_id") or "", row.get("offer_id") or "", row["created_at"],
        ])
    return buf.getvalue()
