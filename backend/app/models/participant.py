import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Participant(Base):
    __tablename__ = "participants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Optional: a candidate may register by email without FSP history and link an FSP account later.
    fsp_id = Column(String(64), unique=True, nullable=True, index=True)
    fsp_linked_at = Column(DateTime(timezone=True))
    display_name = Column(String(200))
    # Login identity. The column holds AES-GCM ciphertext; lookup uses email_bindex.
    email = Column(Text)
    email_bindex = Column(String(64), unique=True)
    password_hash = Column(String(200))
    # Bumped on password reset. Tokens carry the same number and die when it moves.
    token_epoch = Column(Integer, nullable=False, default=0, server_default="0")
    # Bumped when a refresh token is exchanged. The new refresh carries the new number.
    refresh_nonce = Column(Integer, nullable=False, default=0, server_default="0")
    # Bumped on every profile save. A stale form sends the number it loaded and gets a conflict.
    profile_version = Column(Integer, nullable=False, default=0, server_default="0")
    # What the candidate hopes to earn, gross, before tax. Optional. Used only as a hint to employers.
    salary_from_gross = Column(Integer)
    salary_to_gross = Column(Integer)
    email_verified_at = Column(DateTime(timezone=True))
    # Successful password login. Empty means this account has never signed in.
    # The jury button offers the address that has been idle the longest.
    last_login_at = Column(DateTime(timezone=True))
    # Set only for a demo guest account: sessions close at this moment (services/guest.py).
    guest_until = Column(DateTime(timezone=True))
    telegram = Column(Text)
    phone = Column(Text)
    birth_date = Column(Date)
    region = Column(String(100), index=True)
    # The anonymous card omits a field when its switch is off. The score still reads the field,
    # except the city: a hidden city is not a filter the employer can probe.
    show_city = Column(Boolean, nullable=False, default=True, server_default="true")
    show_stack = Column(Boolean, nullable=False, default=True, server_default="true")
    show_fsp = Column(Boolean, nullable=False, default=True, server_default="true")
    show_experience = Column(Boolean, nullable=False, default=True, server_default="true")
    # office / hybrid / remote. Empty means "not chosen" and the search filter does not drop the person.
    work_formats = Column(JSONB, nullable=False, default=list, server_default="[]")
    experience_years = Column(Integer)
    # Names from soft_skills.NAMES. Shown on the card, not used in the score.
    soft_skills = Column(JSONB, nullable=False, default=list, server_default="[]")
    # Subject areas this person does not want to be offered. Codes from INDUSTRIES, never "any".
    excluded_industries = Column(JSONB, nullable=False, default=list, server_default="[]")
    declared_grade = Column(String(20))
    # Survey (TZ 2.1): specialization drives the category and the test blueprint.
    specialization = Column(String(30), index=True)
    industry = Column(String(40))
    work_goal = Column(String(20))   # job | internship | both
    survey_at = Column(DateTime(timezone=True))
    # Set once, on the first saved survey. The 24-hour retest window is counted from it.
    category_opened_at = Column(DateTime(timezone=True))
    # is_visible: anonymous card is searchable by employers; public_profile: named page + leaderboard
    is_visible = Column(Boolean, nullable=False, default=True)
    # active: looking now; open: will consider an offer; not_looking: out of search and shortlists.
    # «Не ищу» does not withdraw the publication consent.
    job_search = Column(String(20), nullable=False, default="open", server_default="open")
    public_profile = Column(Boolean, nullable=False, default=False)
    is_minor = Column(Boolean, nullable=False, default=False)
    minor_consent_given = Column(Boolean, nullable=False, default=False)
    # Legal representative of a candidate aged 15 to 17: who confirmed and when.
    guardian_email = Column(Text)
    guardian_consent_at = Column(DateTime(timezone=True))
    grade_locked_until = Column(DateTime(timezone=True))
    # Grade confirmed by a completed test. It outranks declared_grade and experience in the category:
    # employers must not rank candidates by a self-described grade (TZ section 2).
    assessed_grade = Column(String(20))
    assessed_at = Column(DateTime(timezone=True))
    # Latest short practice task. Shown on the anonymous card; it does not change the grade.
    practice_topic = Column(String(40))
    practice_ok = Column(Boolean)
    practice_at = Column(DateTime(timezone=True))
    # Latest verdict on a task an employer wrote (checked by the system or by that employer). Shown on the card.
    employer_task_title = Column(String(200))
    employer_task_passed = Column(Boolean)
    employer_task_at = Column(DateTime(timezone=True))
    # Set when identifying fields were erased: on account deletion or 30 days after consent withdrawal.
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    qualifications = relationship("Qualification", back_populates="participant", cascade="all, delete")
    results = relationship("Result", back_populates="participant")
    skills = relationship("Skill", back_populates="participant", cascade="all, delete")
    discipline_scores = relationship("DisciplineScore", back_populates="participant", cascade="all, delete")
    category = relationship("CategoryAssignment", back_populates="participant", uselist=False, cascade="all, delete")
    embedding = relationship("ProfileEmbedding", back_populates="participant", uselist=False, cascade="all, delete")
    offers = relationship("Offer", back_populates="candidate", foreign_keys="Offer.candidate_id")
    applications = relationship("Application", back_populates="candidate")
    consent_logs = relationship("ConsentLog", back_populates="participant")

    def minor_now(self, today: date | None = None) -> bool:
        """Age from birth_date. The stored is_minor flag is only a fallback before the date is known."""
        if self.birth_date is None:
            return bool(self.is_minor)
        today = today or date.today()
        birthday = (self.birth_date.month, self.birth_date.day)
        age = today.year - self.birth_date.year - ((today.month, today.day) < birthday)
        return age < 18

    @property
    def discoverable(self) -> bool:
        looking = (self.job_search or "open") != "not_looking"
        return bool(self.is_visible) and looking and (not self.minor_now() or bool(self.minor_consent_given))


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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    participant = relationship("Participant", back_populates="results")
    __table_args__ = (
        UniqueConstraint("participant_id", "event_id", name="uq_result_participant_event"),
    )


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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # When the skill became evidence (a test or a resume quote). A declaration has no such date.
    confirmed_at = Column(DateTime(timezone=True))
    participant = relationship("Participant", back_populates="skills")
    __table_args__ = (UniqueConstraint("participant_id", "name", name="uq_participant_skill"),)
