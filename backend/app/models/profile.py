import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Computed, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class DisciplineScore(Base):
    __tablename__ = "discipline_scores"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False,
                            index=True)
    discipline = Column(String(50), nullable=False)
    score = Column(Float, nullable=False)       # posterior mean (shrunk)
    sigma = Column(Float, nullable=False)       # posterior uncertainty
    lcb = Column(Float, nullable=False)         # score - sigma, used for ranking
    confidence = Column(Float, nullable=False)  # n_eff / (n_eff + k)
    events_count = Column(Integer, nullable=False, default=0)
    team_events_count = Column(Integer, nullable=False, default=0)
    best_rank = Column(String(10))
    top_event_ids = Column(JSONB, nullable=False, default=list)
    scoring_version = Column(String(20), nullable=False)
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    participant = relationship("Participant", back_populates="discipline_scores")
    __table_args__ = (UniqueConstraint("participant_id", "discipline", name="uq_participant_discipline"),)


class CategoryAssignment(Base):
    __tablename__ = "category_assignments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False,
                            unique=True)
    primary_role = Column(String(50), nullable=False)
    grade = Column(String(20), nullable=False)
    grade_source = Column(String(20), nullable=False, default="default")
    stack = Column(JSONB, nullable=False, default=list)
    explanation = Column(JSONB, nullable=False, default=list)
    rules_version = Column(String(20), nullable=False, default="v2.0.0")
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    participant = relationship("Participant", back_populates="category")


class ProfileEmbedding(Base):
    __tablename__ = "profile_embeddings"
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True)
    embedding = Column(Vector(1024), nullable=False)
    model_version = Column(String(100), nullable=False)
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    participant = relationship("Participant", back_populates="embedding")

    __table_args__ = (
        Index("ix_profile_embeddings_hnsw", "embedding", postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


class ProfileSearchIndex(Base):
    __tablename__ = "profile_search_index"
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True)
    skills_text = Column(Text, nullable=False)
    # 'simple' config: the russian stemmer mangles technology names
    skills_tsv = Column(TSVECTOR, Computed("to_tsvector('simple', skills_text)", persisted=True))
    role = Column(String(50))
    grade = Column(String(20))
    region = Column(String(100))
    # FIX BUG-E: onupdate= was missing. Without it, every rebuild_profile UPDATE
    # leaves updated_at frozen at creation time. Incremental sync and freshness
    # monitoring cannot detect stale profiles.
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_psi_skills_tsv", "skills_tsv", postgresql_using="gin"),
        Index("ix_psi_skills_trgm", "skills_text", postgresql_using="gin",
              postgresql_ops={"skills_text": "gin_trgm_ops"}),
    )
