"""Facts a candidate can check before accepting. There is no single score.

Rates use the Wilson lower bound (z = 1.64) and stay hidden until five cases in 180 days,
so one invitation cannot be read out of the number.

Responsiveness to applications (anti-fake-vacancy signal): of the applications to the company's vacancies
in the last 90 days, how many the company opened within 7 days, and the median days to that. An application
younger than 7 days that is still unopened is not counted yet: the company still has time.
"""
from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select

from app.services.matching import wilson_lower

WINDOW_DAYS = 180
MIN_N = 5
Z = 1.64
APPLY_WINDOW_DAYS = 90
REACT_DAYS = 7


def rate(count: int, n: int) -> dict:
    if n < MIN_N:
        return {"shown": False, "n": n, "note": "мало данных"}
    lower = wilson_lower(count, n, z=Z)
    return {"shown": True, "n": n, "count": count, "lower": round(lower, 3) if lower is not None else None}


def responsiveness(applications: Iterable[tuple[datetime, datetime | None]], now: datetime) -> dict:
    """``applications`` are (created_at, viewed_at) pairs. Opening or changing the status sets viewed_at."""
    since = now - timedelta(days=APPLY_WINDOW_DAYS)
    limit = timedelta(days=REACT_DAYS)
    counted = [(made, seen) for made, seen in applications
               if made is not None and made >= since and (seen is not None or now - made >= limit)]
    fast = sum(1 for made, seen in counted if seen is not None and seen - made <= limit)
    out = rate(fast, len(counted))
    out["window_days"], out["within_days"] = APPLY_WINDOW_DAYS, REACT_DAYS
    if out["shown"]:
        waits = [(seen - made).total_seconds() / 86400 for made, seen in counted if seen is not None]
        out["median_days"] = round(statistics.median(waits), 1) if waits else None
    return out


def acceptance(statuses: Iterable[str]) -> dict:
    """Share of the company's answered invitations that candidates accepted (declined ones count, pending do not)."""
    answered = [s for s in statuses if s in ("accepted", "rejected")]
    return rate(sum(1 for s in answered if s == "accepted"), len(answered))


async def applications_by_employer(db, employer_ids: list, now: datetime | None = None) -> dict:
    """Responsiveness for several companies in one query. Missing companies get the «мало данных» block."""
    from app.models import Application, Vacancy

    now = now or datetime.now(UTC)
    found: dict = {eid: [] for eid in employer_ids}
    if employer_ids:
        rows = (await db.execute(
            select(Vacancy.employer_id, Application.created_at, Application.viewed_at)
            .join(Vacancy, Application.vacancy_id == Vacancy.id)
            .where(Vacancy.employer_id.in_(employer_ids),
                   Application.created_at >= now - timedelta(days=APPLY_WINDOW_DAYS)))).all()
        for eid, made, seen in rows:
            found.setdefault(eid, []).append((made, seen))
    return {eid: responsiveness(pairs, now) for eid, pairs in found.items()}


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
    facts = summarize(accepted=len(accepted), replied=len(replied), interviewed=len(met),
                      offers=len(rows), complaints=int(complaints),
                      created_at=employer.created_at, now=now)
    facts["applications"] = (await applications_by_employer(db, [employer.id], now))[employer.id]
    facts["acceptance"] = acceptance(status for _, status in rows)
    return facts
