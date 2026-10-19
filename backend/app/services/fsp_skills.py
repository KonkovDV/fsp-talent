"""A registry result confirms a skill only when every competition in that discipline exercises it.

Product, robotics and unmanned aircraft do not: the protocol names the discipline, not the stack.
A place in the top three of a field of at least MIN_FIELD_FOR_PRIZE, or an assigned rank, counts.
A plain participation does not. A team result does not confirm the skill to one member.
A skill the platform test already checked and did not confirm
stays on the claim: the registry does not erase a measured miss. A test confirmation keeps its label.
"""
from __future__ import annotations

from app.services.scoring.engine import MIN_FIELD_FOR_PRIZE

# Names are this catalog's skills, not a copied table. Data structures sit inside Algorithms.
FSP_SKILLS: dict[str, tuple[str, ...]] = {
    "algorithmic": ("Algorithms",),
    "security": ("Pentesting",),
    "ai": ("Machine Learning",),
}


def skills_for_discipline(discipline: str) -> tuple[str, ...]:
    return FSP_SKILLS.get(discipline, ())


def prize_confirms(place: int, total: int) -> bool:
    return total >= MIN_FIELD_FOR_PRIZE and 1 <= place <= 3


def granted_skills(results: list[tuple[str, int, int, bool]], ranks: list[str]) -> frozenset[str]:
    """``results`` are (discipline, place, field size, team). ``ranks`` are personal ranks."""
    found: set[str] = set()
    for discipline, place, total, team in results:
        if team or not prize_confirms(int(place), int(total)):
            continue
        found.update(skills_for_discipline(discipline))
    for discipline in ranks:
        found.update(skills_for_discipline(discipline))
    return frozenset(found)


def apply_fsp_skills(skills: dict[str, str], granted: frozenset[str],
                     tested: frozenset[str]) -> dict[str, str]:
    """Upgrade claims and fill gaps. Leave a test confirmation and a measured miss alone."""
    out = dict(skills)
    for skill in sorted(granted):
        current = out.get(skill)
        if current == "test_confirmed" or skill in tested:
            continue
        out[skill] = "fsp_confirmed"
    return out
