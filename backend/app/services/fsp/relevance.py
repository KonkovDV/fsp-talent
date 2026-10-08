"""How much of an FSP discipline counts for a need.

The organiser's answer: every discipline is equal, and a result in the discipline that matches
the need counts more than a result in another one. Security work should read a security protocol
ahead of a robotics one. Competition status is not an input and does not change the weight.
"""
from __future__ import annotations

from app.services.categorization import DISCIPLINE_ROLE_MAP

# Fixed before any metric run. Not fitted on the published seeds.
OTHER_DISCIPLINE = 0.5

# Reverse of DISCIPLINE_ROLE_MAP. ML also reads algorithmic programming:
# the AI discipline is new, and the algorithmic protocol is the same kind of evidence.
_EXTRA = {"ml": frozenset({"algorithmic"})}


def relevant_disciplines(role: str | None) -> frozenset[str]:
    if not role:
        return frozenset()
    found = {disc for disc, mapped in DISCIPLINE_ROLE_MAP.items() if mapped == role}
    found.update(_EXTRA.get(role, ()))
    return frozenset(found)


def lcb_for_need(role: str | None, scores: dict[str, float],
                 discipline: str | None = None) -> tuple[float, str | None, str | None]:
    """Return ``(lcb, kind, discipline)``.

    ``kind`` is ``profile`` or ``other`` when the need has profile disciplines and no discipline
    filter is set. It is ``None`` for a manual discipline filter and for a role with no profile
    discipline: the caller keeps the plain FSP line. An empty score map returns 0.
    """
    if discipline:
        return float(scores.get(discipline, 0.0)), None, discipline if discipline in scores else None
    if not scores:
        return 0.0, None, None
    relevant = relevant_disciplines(role)
    if not relevant:
        best = max(scores, key=lambda disc: scores[disc])
        return float(scores[best]), None, best
    profile = {disc: value for disc, value in scores.items() if disc in relevant}
    other = {disc: value for disc, value in scores.items() if disc not in relevant}
    profile_best = max(profile.values()) if profile else None
    other_best = max(other.values()) if other else None
    other_weighted = OTHER_DISCIPLINE * other_best if other_best is not None else None
    if profile_best is None and other_weighted is None:
        return 0.0, None, None
    if other_weighted is None or (profile_best is not None and profile_best >= other_weighted):
        disc = max(profile, key=lambda name: profile[name])
        return float(profile_best), "profile", disc
    disc = max(other, key=lambda name: other[name])
    return float(other_weighted), "other", disc
