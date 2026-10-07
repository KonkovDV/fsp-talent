import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

# One complaint per candidate per invitation or vacancy. The words are the stored reason codes.
REASONS = ("не_вакансия", "сбор_данных", "зарплата_не_та", "оскорбление", "другое")


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint(
            "(offer_id IS NOT NULL AND vacancy_id IS NULL) OR (offer_id IS NULL AND vacancy_id IS NOT NULL)",
            name="ck_complaints_one_object",
        ),
        CheckConstraint(
            "reason IN ('не_вакансия', 'сбор_данных', 'зарплата_не_та', 'оскорбление', 'другое')",
            name="ck_complaints_reason",
        ),
        UniqueConstraint("participant_id", "offer_id", name="uq_complaints_participant_offer"),
        UniqueConstraint("participant_id", "vacancy_id", name="uq_complaints_participant_vacancy"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True)
    vacancy_id = Column(UUID(as_uuid=True), ForeignKey("vacancies.id"), nullable=True)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False, index=True)
    reason = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
