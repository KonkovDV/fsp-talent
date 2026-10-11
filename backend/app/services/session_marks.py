"""Marks that do not move the grade: a hidden tab, a copied stem, and a request to look again."""
from __future__ import annotations

TAB_LEAVE_CAP = 30
INTEGRITY_FACTOR = 0.85
INTEGRITY_LINE = (
    "На тесте отмечены быстрые верные ответы или уход со вкладки. "
    "Место умножено на 0,85. Грейд не изменён."
)
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


def latest_grade_flags(rows: list[tuple]) -> dict:
    """Newest completed grade test per person. Rows are newest first.

    An express trial and a vacancy test are not grade tests, so they neither
    apply the penalty nor hide an earlier grade test that should.
    """
    marks: dict = {}
    for pid, flags in rows:
        if pid in marks:
            continue
        flags = flags or {}
        if flags.get("vacancy_id") or flags.get("mode") == "express":
            continue
        marks[pid] = flags
    return marks


def latest_failed_targets(rows: list[tuple]) -> dict:
    """Target grade of the newest grade test per (person, specialization) when that test was not passed.

    Rows are (participant_id, specialization, target_grade, flags), newest first. An express trial and
    a vacancy test are skipped like in latest_grade_flags. A newer passed or accepted-lower attempt
    hides an older failure: only the newest grade test of the specialization speaks (DoR-N7).
    """
    seen: set = set()
    failed: dict = {}
    for pid, spec, target, flags in rows:
        flags = flags or {}
        if flags.get("vacancy_id") or flags.get("mode") == "express" or not spec:
            continue
        if (pid, spec) in seen:
            continue
        seen.add((pid, spec))
        if flags.get("outcome") == "not_passed" and target:
            failed[(pid, spec)] = target
    return failed


def integrity_flagged(flags: dict | None) -> bool:
    """A grade test with a fast-correct run or a hidden tab. A trial and a vacancy test do not count."""
    flags = flags or {}
    if flags.get("vacancy_id") or flags.get("mode") == "express":
        return False
    return bool(flags.get("pace_review")) or int(flags.get("tab_leaves") or 0) > 0


def penalised(score: float, flags: dict | None) -> tuple[float, str | None]:
    if not integrity_flagged(flags):
        return score, None
    return round(score * INTEGRITY_FACTOR, 4), INTEGRITY_LINE


def dispute_error(status: str, owned: bool, already: bool) -> str | None:
    """Why a dispute is refused, or None when it can be stored."""
    if not owned:
        return "not_found"
    if status != "completed":
        return "not_finished"
    if already:
        return "already"
    return None
