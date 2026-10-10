"""Single code path that turns FSP protocols + confirmed skills into a searchable profile."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import CandidateResume, Participant, Result, Skill, VerifiableCredential
from app.models.profile import CategoryAssignment, DisciplineScore, ProfileEmbedding, ProfileSearchIndex
from app.services.ai.embedder import embed, profile_text
from app.services.categorization import DISCIPLINE_LABELS, assign_category
from app.services.fsp.mock import FSPParticipant, RegistryRank, choose_registry_ranks, get_fsp_adapter
from app.services.scoring.engine import compute_discipline_score
from app.services.search.cache import bump_bank_epoch
from app.services.vc.issuer import issue_achievement_credential


def age_on(birth: date, ref: date) -> int:
    return ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))


def adult_cutoff(today: date | None = None) -> date:
    """Last birth date that is already 18 on `today`. 29 February falls back to 28 February."""
    today = today or date.today()
    try:
        return today.replace(year=today.year - 18)
    except ValueError:
        return date(today.year - 18, 2, 28)


def age_confirmed_adult():
    """SQL: a birth date is on file and that date is already 18. A checkbox is not a date."""
    return and_(Participant.birth_date.is_not(None), Participant.birth_date <= adult_cutoff())


def born_adult(birth: date | None, is_minor: bool, today: date | None = None) -> bool:
    """Birth date wins over the stored flag. The flag is only used when the date is unknown."""
    if birth is None:
        return not is_minor
    return birth <= adult_cutoff(today)


async def ingest_from_fsp(
    db: AsyncSession, data: FSPParticipant, participant: Participant | None = None,
) -> Participant:
    """Create a profile from FSP protocols, or attach them to an account registered by email.

    FSP data is authoritative for the birth date and region; the display name the person chose is kept.
    """
    if participant is None:
        p = Participant(fsp_id=data.fsp_id, display_name=data.display_name)
        db.add(p)
    else:
        p = participant
        p.fsp_id = data.fsp_id
        p.display_name = p.display_name or data.display_name
    p.region = data.region or p.region
    p.birth_date = data.birth_date
    p.is_minor = age_on(data.birth_date, date.today()) < 18
    p.fsp_linked_at = datetime.now(UTC)
    await db.flush()
    for r in data.results:
        res = Result(
            participant_id=p.id, event_id=r.event_id, event_name=r.event_name, discipline=r.discipline,
            competition_status=r.competition_status, place=r.place, total_participants=r.total_participants,
            regions_count=r.regions_count, is_team=r.is_team, team_size=r.team_size, role=r.role,
            event_date=r.event_date, protocol_url=r.protocol_url, trust_level=r.trust_level,
            raw_data={"source": settings.FSP_MODE, "ekp_number": r.ekp_number},
        )
        db.add(res)
        await db.flush()
        vc_id = uuid.uuid4()
        credential = issue_achievement_credential(str(vc_id), str(p.id), {
            "type": "FSPCompetitionResult",
            "source": "ФСП" if settings.FSP_MODE == "real" else "ФСП (тестовый мок)",
            "eventId": r.event_id,
            "eventName": r.event_name,
            "discipline": r.discipline,
            "competitionStatus": r.competition_status,
            "place": r.place,
            "totalParticipants": r.total_participants,
            "teamSize": r.team_size,
            "eventDate": r.event_date.isoformat(),
        })
        db.add(VerifiableCredential(
            id=vc_id, participant_id=p.id, result_id=res.id,
            credential_json=credential,
            proof_value=credential["proof"]["proofValue"],
        ))
    return p


def unseen_results(known_event_ids: set[str], data: FSPParticipant) -> list:
    """Protocol lines the profile does not have yet. A repeat of the same event is not a second result."""
    return [row for row in data.results if row.event_id not in known_event_ids]


async def append_new_results(db: AsyncSession, participant: Participant, data: FSPParticipant) -> int:
    """Add protocol lines that are not stored yet and return how many were added."""
    known = set(await db.scalars(select(Result.event_id).where(Result.participant_id == participant.id)))
    fresh = unseen_results(known, data)
    if not fresh:
        return 0
    original = data.results
    data.results = fresh
    try:
        await ingest_from_fsp(db, data, participant)
    finally:
        data.results = original
    return len(fresh)


async def _registry_ranks(p: Participant, ranks: list[RegistryRank] | None) -> list[RegistryRank] | None:
    """Ranks to write. None means keep the rows already stored (the real registry was not fetched)."""
    if ranks is not None:
        return ranks
    if not p.fsp_id or settings.FSP_MODE == "real":
        return None
    data = await get_fsp_adapter().fetch_participant(p.fsp_id)
    if data is None:
        return None
    return list(data.ranks)


async def rebuild_profile(db: AsyncSession, p: Participant, ranks: list[RegistryRank] | None = None) -> None:
    if p.birth_date is not None:
        p.is_minor = age_on(p.birth_date, date.today()) < 18
        if p.is_minor:
            p.public_profile = False
    # A file the candidate uploaded is a copy, not a registry line. It stays on their page and out of the score.
    results = list(await db.scalars(select(Result).where(
        Result.participant_id == p.id, Result.trust_level == "verified_fsp")))
    skills = [s.name for s in await db.scalars(
        select(Skill).where(Skill.participant_id == p.id, Skill.confirmed.is_(True)))]

    by_disc: dict[str, list] = {}
    for r in results:
        by_disc.setdefault(r.discipline, []).append({
            "id": str(r.id), "place": r.place, "total_participants": r.total_participants,
            "competition_status": r.competition_status, "team_size": r.team_size, "event_date": r.event_date,
        })
    ranks = await _registry_ranks(p, ranks)
    previous: dict[str, tuple] = {}
    if ranks is None:
        for row in await db.scalars(select(DisciplineScore).where(DisciplineScore.participant_id == p.id)):
            previous[row.discipline] = (row.best_rank, row.rank_assigned_at, row.rank_order_ref)
    by_rank = choose_registry_ranks(ranks or [])
    await db.execute(delete(DisciplineScore).where(DisciplineScore.participant_id == p.id))
    scores = []
    for disc, events in by_disc.items():
        sd = compute_discipline_score(events)
        fact = by_rank.get(disc)
        if fact is not None:
            best_rank, assigned_at, order_ref = fact.rank, fact.assigned_at, fact.order_ref
        else:
            best_rank, assigned_at, order_ref = previous.get(disc, (None, None, None))
        db.add(DisciplineScore(
            participant_id=p.id, discipline=disc, best_rank=best_rank,
            rank_assigned_at=assigned_at, rank_order_ref=order_ref, **sd,
        ))
        scores.append({"discipline": disc, **sd})

    cat = assign_category(skills, scores, p.experience_years, p.declared_grade, p.assessed_grade,
                          getattr(p, "specialization", None))
    existing = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == p.id))
    if existing:
        for k, v in cat.items():
            setattr(existing, k, v)
    else:
        db.add(CategoryAssignment(participant_id=p.id, **cat))

    disc_labels = [DISCIPLINE_LABELS[d] for d in by_disc if d in DISCIPLINE_LABELS]
    resume_stack = [name for stack in await db.scalars(
        select(CandidateResume.stack).where(CandidateResume.participant_id == p.id)) for name in (stack or [])]
    skills_text = " ".join(skills + [s for s in resume_stack if s not in skills] + list(by_disc) + disc_labels) or "-"
    psi = await db.get(ProfileSearchIndex, p.id)
    if psi:
        psi.skills_text, psi.role, psi.grade, psi.region = skills_text, cat["primary_role"], cat["grade"], p.region
    else:
        db.add(ProfileSearchIndex(participant_id=p.id, skills_text=skills_text, role=cat["primary_role"],
                                  grade=cat["grade"], region=p.region))

    vec = await embed(profile_text(skills, cat["primary_role"], disc_labels))
    if vec is not None:
        emb = await db.get(ProfileEmbedding, p.id)
        if emb:
            emb.embedding, emb.model_version = vec, settings.EMBEDDING_MODEL
        else:
            db.add(ProfileEmbedding(participant_id=p.id, embedding=vec, model_version=settings.EMBEDDING_MODEL))
    await db.flush()
    await bump_bank_epoch()
