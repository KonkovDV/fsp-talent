"""Single code path that turns FSP protocols + confirmed skills into a searchable profile."""
from __future__ import annotations
import uuid
from datetime import date
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Participant, Result, Skill, VerifiableCredential
from app.models.profile import CategoryAssignment, DisciplineScore, ProfileEmbedding, ProfileSearchIndex
from app.services.ai.embedder import embed, profile_text
from app.services.categorization import DISCIPLINE_LABELS, assign_category
from app.services.fsp.mock import FSPParticipant
from app.services.scoring.engine import compute_discipline_score, rank_equivalent
from app.services.vc.issuer import issue_achievement_credential
from app.core.config import settings


def age_on(birth: date, ref: date) -> int:
    return ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))


async def ingest_from_fsp(db: AsyncSession, data: FSPParticipant) -> Participant:
    p = Participant(
        fsp_id=data.fsp_id, display_name=data.display_name, region=data.region,
        birth_date=data.birth_date, is_minor=age_on(data.birth_date, date.today()) < 18,
    )
    db.add(p)
    await db.flush()
    for r in data.results:
        res = Result(
            participant_id=p.id, event_id=r.event_id, event_name=r.event_name, discipline=r.discipline,
            competition_status=r.competition_status, place=r.place, total_participants=r.total_participants,
            regions_count=r.regions_count, is_team=r.is_team, team_size=r.team_size, role=r.role,
            event_date=r.event_date, protocol_url=r.protocol_url, trust_level=r.trust_level,
            raw_data={"source": settings.FSP_MODE},
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
            "rankEquivalent": rank_equivalent(r.competition_status, r.place, r.total_participants),
        })
        db.add(VerifiableCredential(id=vc_id, participant_id=p.id, result_id=res.id, credential_json=credential,
                                    proof_hex=credential["proof"]["proofValue"]))
    return p


async def rebuild_profile(db: AsyncSession, p: Participant) -> None:
    results = list(await db.scalars(select(Result).where(Result.participant_id == p.id)))
    skills = [s.name for s in await db.scalars(
        select(Skill).where(Skill.participant_id == p.id, Skill.confirmed.is_(True)))]

    by_disc: dict[str, list] = {}
    for r in results:
        by_disc.setdefault(r.discipline, []).append({
            "id": str(r.id), "place": r.place, "total_participants": r.total_participants,
            "competition_status": r.competition_status, "team_size": r.team_size, "event_date": r.event_date,
        })
    await db.execute(delete(DisciplineScore).where(DisciplineScore.participant_id == p.id))
    scores = []
    for disc, events in by_disc.items():
        sd = compute_discipline_score(events)
        db.add(DisciplineScore(participant_id=p.id, discipline=disc, **sd))
        scores.append({"discipline": disc, **sd})

    cat = assign_category(skills, scores, p.experience_years, p.declared_grade)
    existing = await db.scalar(select(CategoryAssignment).where(CategoryAssignment.participant_id == p.id))
    if existing:
        for k, v in cat.items():
            setattr(existing, k, v)
    else:
        db.add(CategoryAssignment(participant_id=p.id, **cat))

    disc_labels = [DISCIPLINE_LABELS[d] for d in by_disc if d in DISCIPLINE_LABELS]
    skills_text = " ".join(skills + list(by_disc) + disc_labels) or "-"
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
