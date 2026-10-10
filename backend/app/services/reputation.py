"""Facts a candidate can check before accepting. There is no single score.

Rates use the Wilson lower bound (z = 1.64) and stay hidden until five cases in 180 days,
so one invitation cannot be read out of the number.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select

from app.services.matching import wilson_lower

WINDOW_DAYS = 180
MIN_N = 5
Z = 1.64


def rate(count: int, n: int) -> dict:
    if n < MIN_N:
        return {"shown": False, "n": n, "note": "мало данных"}
    lower = wilson_lower(count, n, z=Z)
    return {"shown": True, "n": n, "count": count, "lower": round(lower, 3) if lower is not None else None}


def summarize(*, accepted: int, replied: int, interviewed: int, offers: int, complaints: int,
              created_at: datetime | None, now: datetime) -> dict:
    tenure = None if created_at is None else max(0, (now - created_at).days)
    return {
        "tenure_days": tenure,
        "reply": rate(replied, accepted),
        "interview": rate(interviewed, accepted),
        "complaints": rate(complaints, offers),
    }


async def for_employer(db, employer) -> dict:
    from app.models import Complaint, InterviewSlot, Offer, OfferMessage, Vacancy

    now = datetime.now(UTC)
    since = now - timedelta(days=WINDOW_DAYS)
    rows = (await db.execute(
        select(Offer.id, Offer.status).where(Offer.employer_id == employer.id, Offer.created_at >= since))).all()
    accepted = [oid for oid, status in rows if status == "accepted"]
    replied: set = set()
    met: set = set()
    if accepted:
        replied = set(await db.scalars(select(OfferMessage.offer_id).where(
            OfferMessage.offer_id.in_(accepted), OfferMessage.author_role == "employer")))
        met = set(await db.scalars(select(InterviewSlot.offer_id).where(InterviewSlot.offer_id.in_(accepted))))
    complaints = await db.scalar(
        select(func.count(func.distinct(Complaint.id)))
        .select_from(Complaint)
        .outerjoin(Offer, Complaint.offer_id == Offer.id)
        .outerjoin(Vacancy, Complaint.vacancy_id == Vacancy.id)
        .where(Complaint.created_at >= since,
               or_(Offer.employer_id == employer.id, Vacancy.employer_id == employer.id))) or 0
    return summarize(accepted=len(accepted), replied=len(replied), interviewed=len(met),
                     offers=len(rows), complaints=int(complaints),
                     created_at=employer.created_at, now=now)
