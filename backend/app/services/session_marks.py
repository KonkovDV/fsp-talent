"""Marks that do not move the grade: a hidden tab, a copied stem, and a request to look again."""
from __future__ import annotations

TAB_LEAVE_CAP = 30
COPY_CAP = 30
DISPUTE_TEXT = (
    "Решение принято автоматически по правилам теста. "
    "Пересмотр — вручную в течение 5 рабочих дней. Пересдача доступна по обычным правилам. "
    "Грейд этой кнопкой не меняется."
)


def note_tab_leave(flags: dict | None) -> dict:
    """Count one hide of the test tab. The grade fields are not touched."""
    out = dict(flags or {})
    out["tab_leaves"] = min(TAB_LEAVE_CAP, int(out.get("tab_leaves") or 0) + 1)
    return out


def note_copy(flags: dict | None) -> dict:
    """Count one copy of the question text. The grade fields are not touched."""
    out = dict(flags or {})
    out["copies"] = min(COPY_CAP, int(out.get("copies") or 0) + 1)
    return out


def dispute_error(status: str, owned: bool, already: bool) -> str | None:
    """Why a dispute is refused, or None when it can be stored."""
    if not owned:
        return "not_found"
    if status != "completed":
        return "not_finished"
    if already:
        return "already"
    return None
