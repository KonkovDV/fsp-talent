"""Skills passport: one signed card with the tested grades, the tested skills and the FSP results.

The card names no person: the subject is the passport id, not the participant id, and there is no
name, region or event title. The candidate hands out the link; a new passport revokes the old one.
"""
import uuid
from collections.abc import Iterable

from app.services.categorization import DISCIPLINE_LABELS
from app.services.fsp.mock import STATUS_LABELS
from app.services.search.pipeline import _bucket
from app.services.survey import SPECIALIZATIONS
from app.services.vc.issuer import issue_achievement_credential

PASSPORT_TYPE = "FSPSkillPassport"
SKILLS_MAX = 30
_BUCKET_ORDER = ("топ-1%", "топ-5%", "топ-10%", "топ-25%", "топ-50%", "участие")


def passport_claims(confirmations: Iterable, skills: Iterable, results: Iterable) -> dict:
    grades = sorted(
        ({"specialization": SPECIALIZATIONS.get(c.specialization, c.specialization), "grade": c.grade,
          "confirmedOn": c.confirmed_at.date().isoformat()} for c in confirmations),
        key=lambda g: g["specialization"])
    tested = sorted({s.name for s in skills if s.trust_level == "test_confirmed"}, key=str.lower)[:SKILLS_MAX]
    per_discipline: dict[str, dict] = {}
    for r in results:
        label = DISCIPLINE_LABELS.get(r.discipline, r.discipline)
        row = per_discipline.setdefault(label, {"discipline": label, "results": 0, "bestBucket": "участие",
                                                "statuses": set(), "lastYear": r.event_date.year})
        row["results"] += 1
        bucket = _bucket(r.place, r.total_participants)
        if _BUCKET_ORDER.index(bucket) < _BUCKET_ORDER.index(row["bestBucket"]):
            row["bestBucket"] = bucket
        row["statuses"].add(STATUS_LABELS.get(r.competition_status, r.competition_status))
        row["lastYear"] = max(row["lastYear"], r.event_date.year)
    fsp = [{**row, "statuses": sorted(row["statuses"])}
           for row in sorted(per_discipline.values(), key=lambda x: (-x["results"], x["discipline"]))]
    return {"grades": grades, "testedSkills": tested, "fspResults": fsp}


def issue_passport(passport_id: uuid.UUID, claims: dict, status_index: int | None = None) -> dict:
    return issue_achievement_credential(str(passport_id), str(passport_id), {
        "type": PASSPORT_TYPE,
        "name": "Паспорт навыков ФСП",
        **claims,
        "criteria": {"narrative": "Грейды и навыки подтверждены тестом платформы, результаты взяты из "
                                  "протоколов ФСП. Имени, контактов и названий соревнований в паспорте нет."},
    }, status_index=status_index)


def is_passport(credential: dict) -> bool:
    achievement = (credential.get("credentialSubject") or {}).get("achievement") or {}
    kind = achievement.get("type") or []
    return PASSPORT_TYPE in kind if isinstance(kind, list) else kind == PASSPORT_TYPE
