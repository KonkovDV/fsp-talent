import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant
from app.api.errors import ApiError
from app.core.config import settings
from app.core.database import get_db
from app.core.ratelimit import too_many
from app.models import ConsentLog, Participant, VerifiableCredential
from app.models.assessment import GradeConfirmation
from app.models.participant import Result, Skill, adult_confirmed
from app.services.passport import PASSPORT_TYPE, issue_passport, passport_claims
from app.services.vc.issuer import verify_credential

router = APIRouter(tags=["passport"])

ISSUES_PER_HOUR = 10


def _is_passport():
    return VerifiableCredential.credential_json.contains(
        {"credentialSubject": {"achievement": {"type": [PASSPORT_TYPE]}}})


def passport_url(passport_id: uuid.UUID) -> str:
    return f"{settings.PUBLIC_BASE_URL}/passport/{passport_id}"


def _out(vc: VerifiableCredential) -> dict:
    return {"id": str(vc.id), "url": passport_url(vc.id), "credential": vc.credential_json,
            "issued_at": vc.issued_at.isoformat() if vc.issued_at else None}


def _me(current: dict) -> uuid.UUID:
    try:
        return uuid.UUID(current["sub"])
    except ValueError as exc:
        raise ApiError(401, "unauthorized") from exc


async def _active(db: AsyncSession, pid: uuid.UUID) -> list[VerifiableCredential]:
    rows = await db.scalars(select(VerifiableCredential).where(
        VerifiableCredential.participant_id == pid, VerifiableCredential.revoked_at.is_(None), _is_passport(),
    ).order_by(VerifiableCredential.issued_at.desc()))
    return list(rows)


@router.get("/candidates/me/passport")
async def my_passport(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    """The current passport, or null when there is none or it was revoked."""
    active = await _active(db, _me(current))
    return _out(active[0]) if active else None


@router.post("/candidates/me/passport", status_code=201)
async def issue_my_passport(current: dict = Depends(get_current_participant), db: AsyncSession = Depends(get_db)):
    """Sign a fresh passport from today's profile. The previous link stops being valid."""
    pid = _me(current)
    person = await db.get(Participant, pid)
    if person is None or person.deleted_at is not None:
        raise ApiError(404, "not_found", "Профиль не найден")
    if not adult_confirmed(person):
        raise ApiError(403, "forbidden", "Паспорт навыков доступен с 18 лет, после указания даты рождения")
    if await too_many(f"passport:{pid}", limit=ISSUES_PER_HOUR, window_seconds=3600):
        raise ApiError(429, "rate_limited", "Слишком часто: паспорт можно выпускать до 10 раз в час")
    confirmations = await db.scalars(select(GradeConfirmation).where(GradeConfirmation.participant_id == pid))
    skills = await db.scalars(select(Skill).where(Skill.participant_id == pid))
    results = await db.scalars(select(Result).where(Result.participant_id == pid))
    claims = passport_claims(list(confirmations), list(skills), list(results))
    if not (claims["grades"] or claims["testedSkills"] or claims["fspResults"]):
        raise ApiError(409, "conflict", "Пока нечего подтверждать: пройдите тест или привяжите ФСП ID")
    now = datetime.now(UTC)
    for old in await _active(db, pid):
        old.revoked_at = now
    passport_id = uuid.uuid4()
    from app.services.vc.status_list import allocate_index
    status_index = await allocate_index(db)
    credential = issue_passport(passport_id, claims, status_index=status_index)
    vc = VerifiableCredential(id=passport_id, participant_id=pid, credential_json=credential,
                              proof_value=credential["proof"]["proofValue"], issued_at=now,
                              status_index=status_index)
    db.add(vc)
    db.add(ConsentLog(participant_id=pid, event_type="passport_issued", actor_id=pid,
                      meta={"credential_id": str(passport_id)}))
    await db.commit()
    return _out(vc)


@router.get("/public/passport/{passport_id}")
async def public_passport(passport_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """What a QR scan opens. The answer has the signed card and its check, never the holder."""
    vc = await db.get(VerifiableCredential, passport_id)
    if vc is None or not vc.credential_json or vc.result_id is not None:
        raise ApiError(404, "not_found", "Паспорт не найден")
    person = await db.get(Participant, vc.participant_id)
    if person is None or person.deleted_at is not None or not adult_confirmed(person):
        raise ApiError(404, "not_found", "Паспорт не найден")
    achievement = vc.credential_json.get("credentialSubject", {}).get("achievement", {})
    if PASSPORT_TYPE not in (achievement.get("type") or []):
        raise ApiError(404, "not_found", "Паспорт не найден")
    signed = verify_credential(vc.credential_json)
    revoked = vc.revoked_at is not None
    return {"valid": signed and not revoked, "signature": signed, "revoked": revoked,
            "issued_at": vc.issued_at.isoformat() if vc.issued_at else None,
            "credential": vc.credential_json}
