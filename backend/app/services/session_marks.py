"""Marks that do not move the grade: a hidden tab, a copied stem, a paste, the risk level, a request to look again."""
from __future__ import annotations

TAB_LEAVE_CAP = 30
INTEGRITY_FACTOR = 0.85
INTEGRITY_LINE = (
    "На тесте несколько сигналов нечестного прохождения (уровень риска «умеренный» или выше). "
    "Место и оценка соответствия не изменены: сигнал сам по себе не доказательство. Грейд не изменён."
)
COPY_CAP = 30
PASTE_CAP = 30
# Integrity risk level (W6): points from independent signals, one signal alone is not a violation
# (Codility Integrity Risk, HackerRank). From "moderate" up the card carries a note. The note does
# not change the grade or the match score until a reviewed field study says the signal is fair.
LEVELS = ((4, "high"), (2, "moderate"), (1, "low"), (0, "none"))
LEVEL_LABELS = {"none": "нет", "low": "низкий", "moderate": "умеренный", "high": "высокий"}
PENALISED_LEVELS = ("moderate", "high")
SIGNAL_LABELS = {
    "tab_leaves": "вкладка теста скрывалась 2 и более раз",
    "copies": "текст задания копировали",
    "pastes": "в поле ответа вставляли текст",
    "fast_correct": "быстрые верные ответы на трудные задания",
    "similarity": "ответ совпал с ключом другого варианта или подпись задания не сошлась",
    "twin": "ответ совпал с числом из копии условия, которого не было на экране",
}
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


def note_paste(flags: dict | None) -> dict:
    """Count one paste into an answer field. The grade fields are not touched."""
    out = dict(flags or {})
    out["pastes"] = min(PASTE_CAP, int(out.get("pastes") or 0) + 1)
    return out


def integrity_level(flags: dict | None) -> dict:
    """Deterministic risk level from signal points. A trial and a vacancy test get no level.

    tab hidden ≥ 2 times: 1; stem copied: 1; paste into an answer: 1; ≥ 2 fast right answers on items the
    candidate was unlikely to solve (or a fast run in one family): 2; key of another variant or a broken
    item signature: 2. 0 → none, 1 → low, 2–3 → moderate, ≥ 4 → high.
    """
    flags = flags or {}
    if flags.get("vacancy_id") or flags.get("mode") == "express":
        return {"level": "none", "points": 0, "signals": []}
    points = {
        "tab_leaves": 1 if int(flags.get("tab_leaves") or 0) >= 2 else 0,
        "copies": 1 if int(flags.get("copies") or 0) > 0 else 0,
        "pastes": 1 if int(flags.get("pastes") or 0) > 0 else 0,
        "fast_correct": 2 if int(flags.get("fast_correct") or 0) >= 2 or flags.get("pace_review") else 0,
        "similarity": 2 if flags.get("variant_review") or flags.get("integrity_review") else 0,
        "twin": 2 if flags.get("twin_review") else 0,
    }
    total = sum(points.values())
    level = next(name for floor, name in LEVELS if total >= floor)
    return {"level": level, "points": total, "signals": [k for k, v in points.items() if v]}


def integrity_line(flags: dict | None) -> str | None:
    """What the candidate and the employer read: the level and the signals, never «you cheated»."""
    info = integrity_level(flags)
    if info["level"] == "none":
        return None
    signals = "; ".join(SIGNAL_LABELS[s] for s in info["signals"])
    tail = " Место и оценка соответствия не меняются." if info["level"] in PENALISED_LEVELS else " Место не меняется."
    return f"Уровень риска честности: {LEVEL_LABELS[info['level']]} ({signals}).{tail} Грейд не изменён."


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
    hides an older failure: only the newest grade test of the specialization speaks.
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
    """A grade test at risk level «moderate» or higher. A trial and a vacancy test do not count."""
    return integrity_level(flags)["level"] in PENALISED_LEVELS


# Browser signals stay a note until a reviewed field study turns this on deliberately.
APPLY_INTEGRITY_FACTOR = False


def penalised(score: float, flags: dict | None) -> tuple[float, str | None]:
    """Employer ranking. While the factor is off, browser signals do not change the score or the card text.

    The candidate still reads integrity_line on their own result. A visible risk label in search would
    punish the person before anyone has reviewed the signal.
    """
    if not APPLY_INTEGRITY_FACTOR or not integrity_flagged(flags):
        return score, None
    return round(score * INTEGRITY_FACTOR, 4), integrity_line(flags) or INTEGRITY_LINE


def dispute_error(status: str, owned: bool, already: bool) -> str | None:
    """Why a dispute is refused, or None when it can be stored."""
    if not owned:
        return "not_found"
    if status != "completed":
        return "not_finished"
    if already:
        return "already"
    return None
