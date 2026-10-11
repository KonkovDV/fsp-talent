"""Match an open vacancy to one candidate profile. Same axes as employer search, reversed."""
from __future__ import annotations

from app.services.categorization import DISCIPLINE_LABELS
from app.services.matching import grade_matches
from app.services.scoring.engine import RANK_ORDER, rank_at_least
from app.services.skills import normalize_skill
from app.services.survey import SPECIALIZATIONS

GRADE_RU = {"intern": "стажёр", "junior": "джуниор", "middle": "мидл", "senior": "сеньор", "lead": "лид"}


def match_vacancy(candidate: dict, vacancy: dict) -> dict | None:
    """Return a card when hard filters pass (open, minors, role, confirmed grade), otherwise None.

    candidate keys: role, grade (confirmed by a test only; a declared grade is passed as None), skills,
    disciplines [{discipline, best_rank}], is_minor
    vacancy keys: role, grade, discipline, min_rank, skills, allows_minors, is_open, plus display fields
    """
    if not vacancy.get("is_open", True):
        return None
    if candidate.get("is_minor") and not vacancy.get("allows_minors"):
        return None
    role = vacancy.get("role")
    if role and candidate.get("role") and role != candidate["role"]:
        return None
    mode = vacancy.get("grade_match") or "plus_minus"
    # No grade yet (no test passed): the candidate still sees the published list and can apply (ТЗ 2.1).
    ungraded = not candidate.get("grade")
    if not ungraded and not grade_matches(candidate.get("grade"), vacancy.get("grade"), mode):
        return None
    # ТЗ 2: FSP results raise a candidate, they never gate one (SDK-01). A discipline or a minimum rank on the
    # vacancy only orders the list and explains the card; a candidate without FSP history sees and applies.
    disciplines = candidate.get("disciplines") or []
    disc = vacancy.get("discipline")
    fsp_match = False
    if disc:
        row = next((d for d in disciplines if d.get("discipline") == disc), None)
        minimum = vacancy.get("min_rank")
        fsp_match = row is not None and (minimum not in RANK_ORDER or rank_at_least(row.get("best_rank"), minimum))
    wanted = {n for raw in (vacancy.get("skills") or []) if (n := normalize_skill(str(raw)))}
    have = wanted & set(candidate.get("skills") or [])
    why = []
    if wanted:
        matched = ", ".join(sorted(have))
        why.append(f"Навыки: {len(have)} из {len(wanted)}" + (f" ({matched})" if matched else ""))
    if role and candidate.get("role") == role:
        why.append(f"Специализация совпадает: {SPECIALIZATIONS.get(role, role)}")
    if ungraded and vacancy.get("grade") and mode != "any":
        why.append("Грейд ещё не подтверждён тестом, вакансия ждёт "
                   f"{GRADE_RU.get(vacancy['grade'], vacancy['grade'])}")
    elif vacancy.get("grade") and mode != "any":
        why.append("Грейд совпадает" if mode == "exact" else f"Грейд не дальше одного шага от {vacancy['grade']}")
    if disc:
        label = DISCIPLINE_LABELS.get(disc, disc).lower()
        if fsp_match:
            why.append(f"Есть результаты ФСП: {label}")
        else:
            why.append(f"Результаты ФСП ({label}) дают преимущество, но не обязательны")
    return {
        "coverage": len(have),
        "wanted": len(wanted),
        "matched_skills": sorted(have),
        "missing_skills": sorted(wanted - have),
        "fsp_match": fsp_match,
        "why": why,
        # Without a test there is no grade to match: the list is the published one, newest first.
        "match": "not_assessed" if ungraded else "matched",
        # Seeing is open, applying to a graded vacancy is not: otherwise skipping the test would beat taking it.
        "needs_test": bool(ungraded and vacancy.get("grade") and mode != "any"),
    }


_STILL_OPEN = frozenset({"applied", "reviewing", "invited"})


def status_after_close(status: str) -> str | None:
    """A closed vacancy ends an application that is still in progress. A refusal stays a refusal."""
    if status in _STILL_OPEN:
        return "closed"
    return None
