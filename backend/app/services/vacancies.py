"""Match an open vacancy to one candidate profile. Same axes as employer search, reversed."""
from __future__ import annotations

from app.services.categorization import DISCIPLINE_LABELS
from app.services.matching import grade_matches
from app.services.scoring.engine import RANK_ORDER, rank_at_least
from app.services.skills import normalize_skill
from app.services.survey import SPECIALIZATIONS


def match_vacancy(candidate: dict, vacancy: dict) -> dict | None:
    """Return a card when hard filters pass, otherwise None.

    candidate keys: role, grade, skills, disciplines [{discipline, best_rank}], is_minor
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
    if not grade_matches(candidate.get("grade"), vacancy.get("grade"), mode):
        return None
    disciplines = candidate.get("disciplines") or []
    disc = vacancy.get("discipline")
    if disc:
        row = next((d for d in disciplines if d.get("discipline") == disc), None)
        if row is None:
            return None
        minimum = vacancy.get("min_rank")
        if minimum in RANK_ORDER and not rank_at_least(row.get("best_rank"), minimum):
            return None
    wanted = {n for raw in (vacancy.get("skills") or []) if (n := normalize_skill(str(raw)))}
    have = wanted & set(candidate.get("skills") or [])
    why = []
    if wanted:
        matched = ", ".join(sorted(have))
        why.append(f"Навыки: {len(have)} из {len(wanted)}" + (f" ({matched})" if matched else ""))
    if role and candidate.get("role") == role:
        why.append(f"Специализация совпадает: {SPECIALIZATIONS.get(role, role)}")
    if vacancy.get("grade") and mode != "any":
        why.append("Грейд совпадает" if mode == "exact" else f"Грейд не дальше одного шага от {vacancy['grade']}")
    if disc:
        why.append(f"Есть результаты ФСП: {DISCIPLINE_LABELS.get(disc, disc).lower()}")
    return {
        "coverage": len(have),
        "wanted": len(wanted),
        "matched_skills": sorted(have),
        "missing_skills": sorted(wanted - have),
        "why": why,
    }


_STILL_OPEN = frozenset({"applied", "reviewing", "invited"})


def status_after_close(status: str) -> str | None:
    """A closed vacancy ends an application that is still in progress. A refusal stays a refusal."""
    if status in _STILL_OPEN:
        return "closed"
    return None
