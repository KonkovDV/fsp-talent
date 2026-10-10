from app.models.assessment import (
    GradeConfirmation,
    GradeDispute,
    ItemStat,
    PracticeAttempt,
    TestSession,
    TestSessionItem,
)
from app.models.audit import AccessLog, ConsentLog
from app.models.complaint import Complaint
from app.models.employer import Employer
from app.models.favorite import EmployerFavorite
from app.models.identity import Consent, EmailVerification
from app.models.interview import InterviewSlot
from app.models.item_draft import ItemDraft
from app.models.need import Need, NeedShortlist, NeedVersion
from app.models.notification import Notification
from app.models.offer import Offer, OfferMessage
from app.models.participant import Participant, Qualification, Result, Skill
from app.models.profile import CategoryAssignment, DisciplineScore, ProfileEmbedding, ProfileSearchIndex
from app.models.task import EmployerTask, TaskSubmission
from app.models.vacancy import Application, Vacancy
from app.models.vc import VerifiableCredential

__all__ = [
    "AccessLog",
    "Application",
    "CategoryAssignment",
    "Complaint",
    "Consent",
    "ConsentLog",
    "DisciplineScore",
    "EmailVerification",
    "Employer",
    "EmployerFavorite",
    "EmployerTask",
    "GradeConfirmation",
    "GradeDispute",
    "InterviewSlot",
    "ItemDraft",
    "ItemStat",
    "Need",
    "NeedShortlist",
    "NeedVersion",
    "Notification",
    "Offer",
    "OfferMessage",
    "Participant",
    "PracticeAttempt",
    "ProfileEmbedding",
    "ProfileSearchIndex",
    "Qualification",
    "Result",
    "Skill",
    "TaskSubmission",
    "TestSession",
    "TestSessionItem",
    "Vacancy",
    "VerifiableCredential",
]

from app.services.field_cipher import install as _install_field_cipher

_install_field_cipher()
