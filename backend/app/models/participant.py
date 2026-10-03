import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class Participant(Base):
    __tablename__ = "participants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fsp_id = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(200))
    email = Column(String(200), unique=True)
    telegram = Column(String(64))
    phone = Column(String(20))
    birth_date = Column(Date)
    region = Column(String(100), index=True)
    experience_years = Column(Integer)
    declared_grade = Column(String(20))
    # is_visible: anonymous card is searchable by employers; public_profile: named page + leaderboard
    is_visible = Column(Boolean, nullable=False, default=True)
    public_profile = Column(Boolean, nullable=False, default=False)
    is_minor = Column(Boolean, nullable=False, default=False)
    minor_consent_given = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
    qualifications = relationship("Qualification", back_populates="participant", cascade="all, delete")
    results = relationship("Result", back_populates="participant")
    skills = relationship("Skill", back_populates="participant", cascade="all, delete")
    discipline_scores = relationship("DisciplineScore", back_populates="participant", cascade="all, delete")
    category = relationship("CategoryAssignment", back_populates="participant", uselist=False, cascade="all, delete")
    embedding = relationship("ProfileEmbedding", back_populates="participant", uselist=False, cascade="all, delete")
    offers = relationship("Offer", back_populates="candidate", foreign_keys="Offer.candidate_id")
    consent_logs = relationship("ConsentLog", back_populates="participant")

    @property
    def discoverable(self) -> bool:
        return self.is_visible and (not self.is_minor or self.minor_consent_given)


class Qualification(Base):
    __tablename__ = "qualifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    discipline = Column(String(50), nullable=False)
    rank = Column(String(10), nullable=False)
    issued_date = Column(Date)
    certificate_number = Column(String(50))
    participant = relationship("Participant", back_populates="qualifications")


class Result(Base):
    """Append-only table -- never UPDATE or DELETE."""
    __tablename__ = "results"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False, index=True)
    event_id = Column(String(100), nullable=False)
    event_name = Column(String(300), nullable=False)
    discipline = Column(String(50), nullable=False)
    competition_status = Column(String(30), nullable=False)
    place = Column(Integer, nullable=False)
    total_participants = Column(Integer, nullable=False)
    regions_count = Column(Integer)
    is_team = Column(Boolean, nullable=False, default=False)
    team_size = Column(Integer, nullable=False, default=1)
    role = Column(String(20), nullable=False, default="participant")
    event_date = Column(Date, nullable=False)
    protocol_url = Column(String(500))
    trust_level = Column(String(20), nullable=False, default="verified_fsp")
    raw_data = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    participant = relationship("Participant", back_populates="results")


class Skill(Base):
    __tablename__ = "skills"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False,
                            index=True)
    name = Column(String(100), nullable=False)
    raw_name = Column(String(200))
    source_quote = Column(Text)
    trust_level = Column(String(20), nullable=False, default="self_reported")
    confirmed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    participant = relationship("Participant", back_populates="skills")
    __table_args__ = (UniqueConstraint("participant_id", "name", name="uq_participant_skill"),)
